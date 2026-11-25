#include "windows_utf.hpp"
#include "pca.hpp"
#include "sampling.hpp"
#include <llama.h>
#include <ggml-backend.h>
#include <json.hpp>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string_view>
#include <thread>

using json = nlohmann::json;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

struct Options {
    std::string model, out, prompt = "The capital of Pakistan is";
    int tokens = 24, layer = -1, gpu = 99, seed = 42;
    double temp = 1.0;
    bool attention = true, paths = true, raw = false, chat = false, all_layers = false;
    bool model_thinking = false, direct_answer = false;
};

static int integer(const std::string& s, int lo, int hi) {
    size_t end = 0; int v = std::stoi(s, &end);
    if (end != s.size() || v < lo || v > hi) throw std::runtime_error("Integer out of range: " + s);
    return v;
}
static Options parse(const std::vector<std::string>& args) {
    Options o;
    for (size_t i = 0; i < args.size(); ++i) {
        const auto& a = args[i];
        auto value = [&]() {
            if (++i == args.size()) throw std::runtime_error("Missing value after " + a);
            return args[i];
        };
        if (a == "--model") o.model = value();
        else if (a == "--out") o.out = value();
        else if (a == "--prompt") o.prompt = value();
        else if (a == "--tokens") o.tokens = integer(value(),0,256);
        else if (a == "--layer") o.layer = integer(value(),-1,2047);
        else if (a == "--gpu-layers") o.gpu = integer(value(),0,2048);
        else if (a == "--seed") o.seed = integer(value(),0,2147483647);
        else if (a == "--temperature") {
            auto s = value(); size_t end = 0; o.temp = std::stod(s, &end);
            if (end != s.size() || !std::isfinite(o.temp) || o.temp < 0 || o.temp > 4) throw std::runtime_error("Temperature must be in [0,4]");
        } else if (a == "--no-attention") o.attention = false;
        else if (a == "--all-layers") o.all_layers = true;
        else if (a == "--no-paths") o.paths = false;
        else if (a == "--raw") o.raw = true;
        else if (a == "--chat") o.chat = true;
        else if (a == "--model-thinking") o.model_thinking = true;
        else if (a == "--direct-answer") o.direct_answer = true;
        else throw std::runtime_error("Unknown argument: " + a);
    }
    if (o.all_layers && !o.attention) throw std::runtime_error("All-layer capture requires attention.");
    if (o.model_thinking && o.direct_answer) throw std::runtime_error("Choose only one assistant prefix.");
    if (!o.chat && (o.model_thinking || o.direct_answer)) throw std::runtime_error("An assistant prefix requires --chat.");
    if (o.model.empty() || o.prompt.empty()) throw std::runtime_error("Provide a GGUF file and a nonempty prompt.");
    if (o.prompt.size() > 65536) throw std::runtime_error("Prompt exceeds 64 KiB.");
    if (!o.out.empty() && fs::exists(fs::u8path(o.out))) throw std::runtime_error("Trace already exists. Choose a new --out path.");
    return o;
}
static std::string piece(const llama_vocab* vocab, int token) {
    std::string s(64, '\0');
    int n = llama_token_to_piece(vocab, token, s.data(), int(s.size()), 0, true);
    if (n < 0) { s.resize(-n); n = llama_token_to_piece(vocab, token, s.data(), int(s.size()), 0, true); }
    if (n < 0) throw std::runtime_error("Cannot decode token piece");
    s.resize(n); return s;
}
static std::string hex_bytes(const std::string& s) {
    const char* digits="0123456789abcdef"; std::string bytes;
    for (unsigned char ch : s) { bytes += digits[ch>>4]; bytes += digits[ch&15]; }
    return bytes;
}
static std::vector<llama_token> tokenize(const llama_vocab* vocab, const std::string& text, bool special) {
    int n = llama_tokenize(vocab, text.data(), int(text.size()), nullptr, 0, true, special);
    if (n >= 0 || n == INT32_MIN) throw std::runtime_error("Prompt cannot be tokenized");
    std::vector<llama_token> ids(-n);
    n = llama_tokenize(vocab, text.data(), int(text.size()), ids.data(), int(ids.size()), true, special);
    if (n <= 0) throw std::runtime_error("Prompt cannot be tokenized");
    ids.resize(n); return ids;
}
static std::string format_chat(llama_model* model, const Options& o) {
    const char* tmpl = llama_model_chat_template(model,nullptr);
    if (!tmpl) throw std::runtime_error("GGUF has no chat template. Choose raw text.");
    const llama_chat_message user{"user",o.prompt.c_str()};
    int n = llama_chat_apply_template(tmpl,&user,1,true,nullptr,0);
    if (n < 1) throw std::runtime_error("This chat template is unsupported. Use raw completion.");
    std::string out(n+1,'\0'); n = llama_chat_apply_template(tmpl,&user,1,true,out.data(),int(out.size()));
    if (n < 1 || n >= int(out.size())) throw std::runtime_error("Cannot apply GGUF chat template");
    out.resize(n);
    if (!o.model_thinking && !o.direct_answer) return out;

    // These optional prefixes are experimental inputs selected by the user.
    const std::string_view source(tmpl);
    constexpr std::string_view assistant = "<|im_start|>assistant\n";
    if (source.find("enable_thinking") == source.npos || source.find("'<think>\\n\\n</think>\\n\\n'") == source.npos ||
        out.size() < assistant.size() || out.compare(out.size()-assistant.size(),assistant.size(),assistant) != 0)
        throw std::runtime_error("This model does not support the selected thinking prefix. Choose None.");
    out += o.model_thinking ? "<think>\n" : "<think>\n\n</think>\n\n";
    return out;
}
static std::atomic<int> offloaded{-1};
static void log_line(enum ggml_log_level level, const char* s, void*) {
    if (const char* p = std::strstr(s,"offloaded ")) {
        int count = -1, total = 0;
        if (std::sscanf(p,"offloaded %d/%d layers",&count,&total)==2) offloaded.store(count);
    }
    if (level >= GGML_LOG_LEVEL_WARN || std::strstr(s,"offloaded ")) std::fputs(s,stderr);
}

struct Probe {
    int keys = 0, heads = 0, width = 0;
    std::string attention_name;
    bool paths = false, all_layers = false;
    std::vector<Vector> weights, residual;
    std::vector<std::vector<Vector>> other;
    std::string failure;

    static bool callback(ggml_tensor* t, bool ask, void* user) noexcept {
        auto& self = *static_cast<Probe*>(user);
        bool selected = !self.attention_name.empty() && self.attention_name == t->name;
        bool attn = selected || (self.all_layers && std::strncmp(t->name,"kq_soft_max-",12)==0);
        bool path = self.paths && std::strncmp(t->name,"l_out-",6)==0;
        if (ask) return attn || path;
        try {
            if (!self.failure.empty()) return false;
            if (t->type != GGML_TYPE_F32 || t->nb[0] != sizeof(float) || t->ne[1] != 1 || t->ne[3] != 1) return true;
            if (attn && t->op == GGML_OP_SOFT_MAX && t->ne[0] >= self.keys && t->ne[2] == self.heads) {
                std::vector<Vector> weights(self.heads, Vector(self.keys));
                for (int h = 0; h < self.heads; ++h) {
                    auto& row = weights[h];
                    ggml_backend_tensor_get(t,row.data(),size_t(h)*t->nb[2],row.size()*sizeof(float));
                    double sum = 0;
                    for (float w : row) {
                        if (!std::isfinite(w) || w < 0 || w > 1.002f) return true;
                        sum += w;
                    }
                    if (std::abs(sum-1.0) > .004) return true;
                }
                if (selected) self.weights = std::move(weights);
                else {
                    char* end=nullptr; long l=std::strtol(t->name+12,&end,10);
                    if (end!=t->name+12 && !*end && l>=0 && size_t(l)<self.other.size()) self.other[l]=std::move(weights);
                }
            }
            if (path && t->ne[0] == self.width && t->ne[2] == 1) {
                char* end = nullptr; long layer = std::strtol(t->name+6,&end,10);
                if (end == t->name+6 || *end || layer < 0 || size_t(layer) >= self.residual.size()) return true;
                Vector row(self.width);
                ggml_backend_tensor_get(t,row.data(),0,row.size()*sizeof(float));
                if (std::all_of(row.begin(),row.end(),[](float v){return std::isfinite(v);})) self.residual[layer] = std::move(row);
            }
        } catch (...) { self.failure = "Cannot read probe tensor"; return false; }
        return true;
    }
};
struct RawFrame {
    json data;
    Vector emb;
    std::vector<Vector> residual;
};
static std::string dump(const json& v) {
    return v.dump(-1,' ',false,json::error_handler_t::replace);
}
class TraceOutput {
    HANDLE file = INVALID_HANDLE_VALUE;
public:
    explicit TraceOutput(const std::string& path) {
        if (path.empty()) return;
        file = CreateFileW(wide(path).c_str(), GENERIC_WRITE, FILE_SHARE_READ,
                           nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE) throw std::runtime_error("Cannot create trace. Choose a new writable path.");
    }
    TraceOutput(const TraceOutput&) = delete;
    TraceOutput& operator=(const TraceOutput&) = delete;
    ~TraceOutput() { if (file != INVALID_HANDLE_VALUE) CloseHandle(file); }
    void operator()(const json& value) {
        if (file == INVALID_HANDLE_VALUE) return;
        const auto line = dump(value) + '\n';
        DWORD written = 0;
        if (line.size() > MAXDWORD || !WriteFile(file, line.data(), DWORD(line.size()), &written, nullptr) || written != line.size())
            throw std::runtime_error("Cannot write the complete trace record.");
    }
};
static int capture(const Options& o) {
    llama_log_set(log_line,nullptr);
    const auto base_dir = application_dir().u8string();
    ggml_backend_load_all_from_path(base_dir.c_str());
    llama_backend_init();
    struct Cleanup { ~Cleanup() { llama_backend_free(); } } cleanup;
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = o.gpu;
    std::cerr << "Loading " << fs::u8path(o.model).filename().u8string() << " ...\n";
    std::unique_ptr<llama_model, decltype(&llama_model_free)> model(llama_model_load_from_file(o.model.c_str(),mp),llama_model_free);
    if (!model) throw std::runtime_error("Cannot load GGUF. See the model loader message above.");
    const auto* vocab = llama_model_get_vocab(model.get());
    int width = llama_model_n_embd_out(model.get()), layers = llama_model_n_layer(model.get()), heads = llama_model_n_head(model.get());
    int layer = o.layer < 0 ? (layers-1)/2 : o.layer;
    if (layer >= layers) throw std::runtime_error("Selected layer exceeds this model's layer count ("+std::to_string(layers)+")");
    auto prompt_ids = tokenize(vocab, o.chat ? format_chat(model.get(),o) : o.prompt, o.chat);
    if (prompt_ids.size() > 128) throw std::runtime_error("Use at most 128 prompt tokens, including chat formatting.");
    const int limit = int(prompt_ids.size()) + o.tokens;
    if (o.all_layers && (limit>96 || int64_t(limit)*(limit+1)/2*layers*heads>8000000))
        throw std::runtime_error("All-layer mode is limited to short traces. Shorten the run or capture one layer.");
    if (limit > llama_model_n_ctx_train(model.get())) throw std::runtime_error("Prompt and generation exceed this model's trained context.");
    Probe probe;
    probe.heads=heads; probe.width=width; probe.paths=o.paths; probe.all_layers=o.all_layers;
    if (o.attention) probe.attention_name = "kq_soft_max-"+std::to_string(layer);
    auto cp = llama_context_default_params();
    cp.n_ctx = uint32_t(std::max(limit,64)); cp.n_batch=1; cp.n_ubatch=1; cp.n_seq_max=1;
    cp.n_threads = cp.n_threads_batch = int(std::min(6u,std::max(1u,std::thread::hardware_concurrency()/2)));
    cp.embeddings = true; cp.pooling_type = LLAMA_POOLING_TYPE_NONE;
    if (o.attention) cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
    if (o.gpu == 0) { cp.offload_kqv=false; cp.op_offload=false; }
    if (o.attention || o.paths) { cp.cb_eval=Probe::callback; cp.cb_eval_user_data=&probe; }
    std::unique_ptr<llama_context, decltype(&llama_free)> ctx(llama_init_from_model(model.get(),cp),llama_free);
    if (!ctx) throw std::runtime_error("Cannot create context. Try fewer GPU layers.");
    char desc[512]{}; llama_model_desc(model.get(),desc,sizeof(desc));
    int n_vocab=llama_vocab_n_tokens(vocab);
    if (width<1 || n_vocab<1) throw std::runtime_error("Model did not expose output dimensions");
    std::cout << "Model: " << desc << "\nEmbedding dimensions: " << width << "\nLayers: " << layers << " | Heads: " << heads << " | Vocab: " << n_vocab << '\n' << std::flush;
    TraceOutput write(o.out);
    std::vector<RawFrame> pending;
    std::unique_ptr<Projection> basis;
    auto emit = [&](RawFrame& f) {
        f.data["xyz"] = basis->project(f.emb);
        auto& path = f.data["path"] = json::array();
        for (size_t l=0; l<f.residual.size(); ++l)
            if (!f.residual[l].empty()) path.push_back({{"layer",l},{"xyz",basis->project(f.residual[l])}});
        if (o.raw) f.data["embedding"] = f.emb;
        write(f.data);
    };
    const int fit_target = std::max(4,int(prompt_ids.size()));
    auto fit = [&] {
        std::vector<Vector> rows;
        for (auto& f : pending) rows.push_back(f.emb);
        basis = std::make_unique<Projection>(rows);
        write({{"event","header"},{"format","tokenscope/1"},{"model",fs::u8path(o.model).filename().u8string()},
               {"description",desc},{"dims",width},{"layers",layers},{"heads",heads},{"vocab",n_vocab},
               {"prompt",o.prompt},{"prompt_tokens",prompt_ids.size()},{"mode",o.chat?"chat":"completion"},
               {"temperature",o.temp},{"seed",o.seed},{"attention_layer",o.attention?layer:-1},{"all_layers",o.all_layers},{"paths_requested",o.paths},
               {"gpu_layers_requested",o.gpu},{"gpu_layers_offloaded",offloaded.load()},
               {"fit_tokens",rows.size()},{"variance",basis->variance},{"raw",o.raw}});
        for (auto& f : pending) emit(f);
        pending.clear();
    };
    std::mt19937 rng(o.seed);
    llama_token current=prompt_ids.front();
    std::string reason="limit"; int emitted=0, attn_frames=0, path_frames=0;
    for (int i=0; i<limit; ++i) {
        probe.keys=i+1; probe.weights.clear(); probe.residual.assign(o.paths?layers:0, {});
        probe.other.assign(o.all_layers?layers:0,{});
        llama_pos pos=i; int8_t output=1; int32_t seq_count=1;
        llama_seq_id seq=0; llama_seq_id* seq_ptr=&seq;
        llama_batch batch{1,&current,nullptr,&pos,&seq_count,&seq_ptr,&output};
        auto begin=Clock::now(); int rc=llama_decode(ctx.get(),batch);
        if (rc!=0 || !probe.failure.empty()) throw std::runtime_error("Decode failed at token "+std::to_string(i)+" (code "+std::to_string(rc)+") "+probe.failure);
        const float* emb=llama_get_embeddings_ith(ctx.get(),0);
        const float* logits=llama_get_logits_ith(ctx.get(),0);
        if (!emb || !logits) throw std::runtime_error("Missing per-token embeddings or logits on this runtime/model.");
        double ms=std::chrono::duration<double,std::milli>(Clock::now()-begin).count();
        RawFrame f; f.emb.assign(emb,emb+width);
        if (!std::all_of(f.emb.begin(),f.emb.end(),[](float v){return std::isfinite(v);})) throw std::runtime_error("Non-finite hidden state");
        f.residual=std::move(probe.residual);
        Distribution dist(logits,n_vocab,o.temp);
        auto candidate = [&](int id) -> json {
            return {{"id",id},{"piece",piece(vocab,id)},{"p",dist.model[id]},{"draw_p",dist.sampling[id]},{"logit",logits[id]}};
        };
        json top=json::array(); for (int id:dist.best) top.push_back(candidate(id));
        std::string decision="end"; int next=-1;
        if (i+1<int(prompt_ids.size())) { next=prompt_ids[i+1]; decision="prompt"; }
        else if (i+1<limit) { next=dist.draw(rng); decision=llama_vocab_is_eog(vocab,next)?"eog":"sample"; }
        const auto token_piece=piece(vocab,current);
        f.data={{"event","token"},{"index",i},{"id",current},{"piece",token_piece},{"piece_hex",hex_bytes(token_piece)},
                {"phase",i<int(prompt_ids.size())?"prompt":"generated"},{"ms",ms},{"entropy_bits",dist.entropy},
                {"attention",std::move(probe.weights)},{"top",std::move(top)},{"decision",decision},
                {"next",next>=0?candidate(next):json(nullptr)}};
        if (o.all_layers) {
            auto& more=f.data["attention_layers"]=json::array();
            for (int l=0; l<layers; ++l) if(!probe.other[l].empty())
                more.push_back({{"layer",l},{"heads",std::move(probe.other[l])}});
        }
        if (!f.data["attention"].empty()) ++attn_frames;
        if (std::any_of(f.residual.begin(),f.residual.end(),[](const Vector& v){return !v.empty();})) ++path_frames;
        if (i+1==int(prompt_ids.size())) {
            std::cout << "Top 5 next tokens after prompt (full-vocabulary softmax):\n";
            for (int id : dist.best) std::cout << "  " << std::setw(7) << id << "  " << std::setw(9) << std::fixed << std::setprecision(4)
                                               << 100*dist.model[id] << "%  " << dump(piece(vocab,id)) << '\n';
            std::cout << std::flush;
        }
        if (basis) emit(f);
        else { pending.push_back(std::move(f)); if (int(pending.size())>=fit_target) fit(); }
        ++emitted;
        if (decision=="eog") { reason="eog"; break; }
        current=next;
    }
    if (!basis) fit();
    write({{"event","end"},{"reason",reason},{"frames",emitted}});
    std::cout << "Frames: " << emitted << " | measured attention: " << attn_frames << " | layer paths: " << path_frames << "\n";
    return 0;
}
int main() {
    try {
        SetConsoleOutputCP(CP_UTF8);
        const auto args=arguments();
        if (args.empty() || std::find(args.begin(),args.end(),"--help")!=args.end()) {
            std::cout << "Capture --model FILE [--prompt TEXT] [--tokens 0..256] [--out NEW.jsonl]\n"
                         "        [--temperature 0..4] [--seed N] [--layer N] [--gpu-layers N]\n"
                         "        [--chat [--model-thinking | --direct-answer]] [--raw] [--all-layers] [--no-attention] [--no-paths]\n"
                         "Default: raw input text, temperature 1. --raw records full vectors.\n"; return 0;
        }
        return capture(parse(args));
    } catch (const std::exception& e) { std::cerr << "Capture: " << e.what() << '\n'; return 1; }
}
