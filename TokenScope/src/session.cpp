#include "session.hpp"
#include <json.hpp>
#include <commdlg.h>
#include <algorithm>
#include <cctype>
#include <sstream>
using json=nlohmann::json;
namespace fs=std::filesystem;

static Candidate candidate(const json& a) {
    return {a.at("id"),a.at("piece"),a.at("p"),a.at("draw_p"),a.at("logit")};
}
static std::string unhex(const std::string& s) {
    std::string bytes;
    auto digit=[](char c){if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("Invalid token bytes");};
    if(s.size()%2) throw std::runtime_error("Invalid token bytes");
    for(size_t i=0;i<s.size();i+=2) bytes+=char(digit(s[i])*16+digit(s[i+1]));
    return bytes;
}
void Trace::line(const std::string& row) {
    if(row.empty()) return;
    if(row.size()>8*1024*1024) throw std::runtime_error("Trace row is too large");
    auto v=json::parse(row); auto type=v.at("event").get<std::string>();
    if(finished) throw std::runtime_error("Extra data after trace end");
    if(type=="header" && !header && v.at("format")=="tokenscope/1") {
        model=v.at("model"); prompt=v.at("prompt"); mode=v.at("mode");
        dims=v.at("dims"); layers=v.at("layers"); heads=v.at("heads"); layer=v.at("attention_layer");
        seed=v.at("seed"); temperature=v.at("temperature"); prompt_tokens=v.at("prompt_tokens");
        fit=v.at("fit_tokens"); gpu=v.at("gpu_layers_offloaded"); variance=v.at("variance").get<Point>(); all_layers=v.value("all_layers",false);
        if(dims<1 || dims>262144 || heads<1 || heads>2048 || layers<1 || layers>2048 || fit<1 ||
           layer < -1 || layer>=layers || prompt_tokens<1 || prompt_tokens>128) throw std::runtime_error("Invalid model metadata");
        header=true; return;
    }
    if(!header) throw std::runtime_error("Expected a TokenScope v1 header");
    if(type=="end") {
        if(v.at("frames")!=frames.size() || frames.empty()) throw std::runtime_error("Incomplete trace");
        reason=v.at("reason"); finished=true; return;
    }
    if(type!="token" || frames.size()>=384 || v.at("index")!=frames.size()) throw std::runtime_error("Invalid token order");
    Frame f; f.index=int(frames.size()); f.id=v.at("id"); f.text=v.at("piece"); f.bytes=unhex(v.at("piece_hex"));
    f.phase=v.at("phase"); f.decision=v.at("decision"); f.xyz=v.at("xyz").get<Point>();
    f.entropy=v.at("entropy_bits"); f.ms=v.at("ms");
    for(auto& c:v.at("top")) f.top.push_back(candidate(c));
    if(f.top.empty() || f.top.size()>5) throw std::runtime_error("Invalid candidate list");
    if(!v.at("next").is_null()) {f.next=candidate(v.at("next")); f.has_next=true;}
    f.attention=v.at("attention").get<std::vector<Vector>>();
    if(!f.attention.empty() && int(f.attention.size())!=heads) throw std::runtime_error("Invalid attention head count");
    for(auto& a:f.attention) if(a.size()!=frames.size()+1) throw std::runtime_error("Invalid attention key positions");
    if(v.contains("attention_layers")) {
        f.other_attention.resize(layers);
        for(auto& item:v["attention_layers"]) {
            int l=item.at("layer"); if(l<0 || l>=layers || l==layer) throw std::runtime_error("Invalid recorded layer");
            auto& rows=f.other_attention[l]; rows=item.at("heads").get<std::vector<Vector>>();
            if(int(rows.size())!=heads) throw std::runtime_error("Invalid layer head count");
            for(const auto& a:rows) if(a.size()!=frames.size()+1) throw std::runtime_error("Invalid layer key positions");
        }
    }
    for(auto& p:v.at("path")) f.path.push_back({p.at("layer"),p.at("xyz").get<Point>()});
    if(v.contains("embedding")) { f.embedding=v["embedding"].get<Vector>(); if(int(f.embedding.size())!=dims) throw std::runtime_error("Invalid raw vector width"); }
    frames.push_back(std::move(f));
}
void Trace::open(const fs::path& file) {
    std::ifstream in(file,std::ios::binary);
    if(!in) throw std::runtime_error("Cannot open trace");
    Trace copy; std::string row;
    while(std::getline(in,row)) copy.line(row);
    if(!copy.finished) throw std::runtime_error("Trace has no completion record");
    *this=std::move(copy);
}
void Session::replay(const fs::path& file) {
    Trace incoming; incoming.open(file);
    cancel(); trace=std::move(incoming); source=file; status="Recorded run";
}
static std::wstring quote(const std::wstring& s) {
    std::wstring result=L"\""; size_t back=0;
    for(wchar_t c:s) {
        if(c==L'\\') {++back; continue;}
        if(c==L'"') result.append(back*2+1,L'\\'); else result.append(back,L'\\');
        result+=c; back=0;
    }
    result.append(back*2,L'\\'); return result+L"\"";
}
void Session::start(const std::vector<std::string>& args) {
    fs::path exe=application_dir()/"Capture.exe";
    if(!fs::exists(exe)) throw std::runtime_error("Place Capture.exe beside TokenScope.exe to run a GGUF.");
    cancel();
    if(scratch.empty()) {
        auto root=fs::temp_directory_path();
        for(unsigned i=0;i<100;++i) {
            auto unique=root/(L"TokenScope-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64())+L"-"+std::to_wstring(i));
            if(fs::create_directory(unique)) { scratch=unique; break; }
        }
        if(scratch.empty()) throw std::runtime_error("Cannot create a temporary trace folder");
    }
    static unsigned run=0;
    auto name=std::to_wstring(++run);
    fs::path path=scratch/(name+L".jsonl"); log=scratch/(name+L".log");
    std::wstring cmd=quote(exe.wstring());
    for(auto& a:args) cmd+=L" "+quote(wide(a));
    cmd+=L" --out "+quote(path.wstring());
    SECURITY_ATTRIBUTES sa{sizeof(sa),nullptr,TRUE};
    HANDLE file=CreateFileW(log.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE) throw std::runtime_error("Cannot create the capture log");
    HANDLE nullin=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_EXISTING,0,nullptr);
    STARTUPINFOW si{}; si.cb=sizeof(si); si.dwFlags=STARTF_USESTDHANDLES; si.hStdInput=nullin; si.hStdError=si.hStdOutput=file;
    PROCESS_INFORMATION pi{};
    BOOL ok=CreateProcessW(exe.c_str(),cmd.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,exe.parent_path().c_str(),&si,&pi);
    CloseHandle(file); if(nullin!=INVALID_HANDLE_VALUE) CloseHandle(nullin);
    if(!ok) throw std::runtime_error("Cannot start Capture.exe");
    CloseHandle(pi.hThread); worker=pi.hProcess;
    trace=Trace{}; source=path; offset=0; fragment.clear(); status="Loading GGUF and fitting the projection...";
}
void Session::cancel() {
    if(!worker) return;
    if(WaitForSingleObject(worker,0)==WAIT_TIMEOUT) TerminateProcess(worker,2);
    WaitForSingleObject(worker,2500); CloseHandle(worker); worker=nullptr;
    if(!trace.finished) status="Capture stopped";
}
static std::string log_tail(const fs::path& file) {
    std::ifstream in(file,std::ios::binary); std::string row,last;
    while(std::getline(in,row)) if(!row.empty()) last=row;
    if(last.size()>230) last=last.substr(last.size()-230); return last;
}
void Session::poll() {
    if(!worker) return;
    bool done=WaitForSingleObject(worker,0)==WAIT_OBJECT_0;
    std::error_code ec; auto size=fs::file_size(source,ec);
    if(!ec && size>offset) {
        std::ifstream in(source,std::ios::binary);
        if(in) {
            in.seekg(std::streamoff(offset));
            std::string part(size_t(std::min<uintmax_t>(size-offset,1024*1024)),'\0');
            in.read(part.data(),std::streamsize(part.size())); part.resize(size_t(in.gcount())); offset+=part.size(); fragment+=part;
            size_t from=0,next;
            while((next=fragment.find('\n',from))!=std::string::npos) {trace.line(fragment.substr(from,next-from)); from=next+1;}
            fragment.erase(0,from);
            if(fragment.size()>8*1024*1024) throw std::runtime_error("Capture produced an oversized row");
            if(trace.header) status="Capturing";
        }
    }
    if(done && (ec || offset>=size)) {
        DWORD code=1; GetExitCodeProcess(worker,&code); CloseHandle(worker); worker=nullptr;
        status=code==0 && trace.finished ? "Capture complete" : "Capture failed. "+log_tail(log);
    }
}
Session::~Session() {
    cancel();
    // Only remove individual run files in this session's own temporary directory.
    std::error_code ec;
    if(!scratch.empty()) {
        for(const auto& e:fs::directory_iterator(scratch,ec))
            if(e.path().extension()==".log" || e.path().extension()==".jsonl") fs::remove(e.path(),ec);
        fs::remove(scratch,ec);
    }
}
fs::path file_dialog(bool save,bool model) {
    std::wstring buf(32768,L'\0'); OPENFILENAMEW of{}; of.lStructSize=sizeof(of);
    of.lpstrFilter=model?L"GGUF models\0*.gguf\0\0":L"TokenScope traces\0*.jsonl\0\0";
    of.lpstrDefExt=model?L"gguf":L"jsonl"; of.lpstrFile=buf.data(); of.nMaxFile=DWORD(buf.size());
    of.Flags=OFN_EXPLORER|OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST|(save?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);
    if(save?GetSaveFileNameW(&of):GetOpenFileNameW(&of)) return fs::path(buf.c_str());
    return {};
}
std::string label(const std::string& s) {
    if(s.empty()) return "(empty)";
    std::string out;
    for(char c:s) {
        if(c=='\n') out+="\\n"; else if(c=='\t') out+="\\t"; else if(c=='\r') out+="\\r";
        else if(c==' ' && out.empty()) out+="\xC2\xB7"; else if(static_cast<unsigned char>(c)<32) out+='?'; else out+=c;
    }
    return out;
}
