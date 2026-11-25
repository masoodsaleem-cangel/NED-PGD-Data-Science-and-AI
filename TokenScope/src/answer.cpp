#include "answer.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <string_view>

void AnswerPath::update(const Trace& trace, int frame, int layer, int head) {
    if (frame < 0 || frame >= static_cast<int>(trace.frames.size())) return;
    if (frame == last_frame && layer == last_layer && head == last_head && branches == last_branches) return;

    // Join only verified sampled transitions, including the first draw from the prompt.
    while (!edges.empty() && edges.back().to > frame) edges.pop_back();
    const int start = std::max({1, trace.prompt_tokens, last_frame + 1});
    for (int i = start; i <= frame; ++i) {
        const auto& before = trace.frames[i - 1];
        const auto& after = trace.frames[i];
        if (after.phase == "generated" && before.decision == "sample" &&
            before.has_next && before.next.id == after.id)
            edges.push_back({i - 1, i});
    }
    last_frame = frame;
    last_head = head;
    last_layer = layer;
    last_branches = branches;
    links.clear();
    origin = -1;
    available = false;
    if (edges.empty() || edges.back().to != frame || branches == BranchView::none) return;

    if (branches == BranchView::attention) {
        // The preceding query sampled this answer token. This token's own
        // attention would belong to the prediction of the following token.
        origin = edges.back().from;
        const auto& rows = trace.frames[origin].weights(layer, trace.layer);
        if (head < 0 || head >= static_cast<int>(rows.size())) return;
        const auto& row = rows[head];
        if (row.size() != static_cast<size_t>(origin + 1)) return;
        available = true;
        for (int i = 0; i <= origin; ++i)
            if (std::isfinite(row[i]) && row[i] > 0) links.push_back({i, row[i]});
    } else {
        origin = frame;
        const auto& query = trace.frames[frame].embedding;
        if (query.empty() || static_cast<int>(query.size()) != trace.dims) return;
        double query_norm = std::inner_product(query.begin(), query.end(), query.begin(), 0.0);
        if (!(query_norm > 0)) return;
        for (int i = 0; i < frame; ++i) {
            const auto& other = trace.frames[i].embedding;
            if (other.size() != query.size()) continue;
            double product = 0, norm = 0;
            for (size_t j = 0; j < query.size(); ++j) {
                product += double(query[j]) * other[j];
                norm += double(other[j]) * other[j];
            }
            if (!(norm > 0)) continue;
            double cosine = product / std::sqrt(norm * query_norm);
            if (std::isfinite(cosine)) links.push_back({i, std::clamp(cosine, -1.0, 1.0)});
        }
        available = !links.empty();
    }
    const auto keep = std::min<size_t>(3, links.size());
    std::partial_sort(links.begin(), links.begin() + keep, links.end(),
        [](const ContextLink& a, const ContextLink& b) {
            if (a.score == b.score) return a.position < b.position;
            return a.score > b.score;
        });
    links.resize(keep);
}

namespace {
constexpr std::string_view open_tag = "<think>", close_tag = "</think>";

bool prompt_opens_thinking(const Trace& trace) {
    std::string prefix;
    if (trace.mode == "chat") {
        for (const auto& token : trace.frames) {
            if (token.phase != "prompt") break;
            prefix += token.bytes;
        }
        // Inspect the assistant prefill, excluding all text from the user's prompt.
        constexpr std::string_view role = "<|im_start|>assistant\n";
        const auto assistant = prefix.rfind(role);
        if (assistant != std::string::npos) prefix.erase(0,assistant+role.size());
        else {
            const auto question = prefix.rfind(trace.prompt);
            if (question == std::string::npos) return false;
            prefix.erase(0,question+trace.prompt.size());
        }
    } else {
        prefix = trace.prompt;
        auto last = prefix.find_last_not_of(" \t\r\n");
        if (last == std::string::npos) return false;
        prefix.resize(last + 1);
        if (prefix.size() < open_tag.size() || prefix.compare(prefix.size() - open_tag.size(), open_tag.size(), open_tag) != 0) return false;
    }
    auto open = prefix.rfind(open_tag), close = prefix.rfind(close_tag);
    return open != std::string::npos && (close == std::string::npos || close < open);
}

// Hold back a delimiter or UTF-8 character that is still arriving across tokens.
size_t complete_prefix(std::string_view s, bool finished) {
    if (finished || s.empty()) return s.size();
    size_t n = s.size();
    for (auto tag : {open_tag, close_tag}) {
        for (size_t k = 1; k < tag.size() && k <= s.size(); ++k)
            if (s.substr(s.size() - k) == tag.substr(0, k)) n = std::min(n, s.size() - k);
    }
    if (n == 0) return 0;
    size_t i = n - 1;
    while (i > 0 && (static_cast<unsigned char>(s[i]) & 0xc0) == 0x80) --i;
    auto b = static_cast<unsigned char>(s[i]);
    size_t bytes = b < 0x80 ? 1 : b < 0xc0 ? 1 : b < 0xe0 ? 2 : b < 0xf0 ? 3 : 4;
    return n - i < bytes ? i : n;
}
}

bool ReplyText::update(const Trace& trace, bool thinking_text, int visible_frames) {
    const int total = static_cast<int>(trace.frames.size());
    const int count = visible_frames < 0 ? total : std::min(total,visible_frames);
    const bool finished = trace.finished && count == total;
    if (last_size == count && last_finished == finished && last_thinking == thinking_text) return false;
    last_size = count;
    last_finished = finished;
    last_thinking = thinking_text;
    answer.clear();
    tagged_thinking.clear();

    in_thinking = count >= trace.prompt_tokens && trace.prompt_tokens > 0 && prompt_opens_thinking(trace);
    saw_thinking = in_thinking;
    std::string generated;
    for (int i = std::max(0, trace.prompt_tokens); i < count; ++i)
        if (trace.frames[i].phase == "generated") generated += trace.frames[i].bytes;
    std::string_view rest(generated.data(), complete_prefix(generated, finished));
    while (!rest.empty()) {
        auto open = rest.find(open_tag), close = rest.find(close_tag);
        size_t next = std::min(open, close);
        auto text = rest.substr(0, next);
        if (!in_thinking) answer.append(text);
        else if (thinking_text) tagged_thinking.append(text);
        if (next == std::string_view::npos) break;
        in_thinking = next == open;
        saw_thinking = saw_thinking || in_thinking;
        rest.remove_prefix(next + (in_thinking ? open_tag.size() : close_tag.size()));
    }
    return true;
}
