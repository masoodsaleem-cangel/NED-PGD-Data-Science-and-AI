#pragma once
#include "session.hpp"

enum class BranchView { attention, similar, none };

struct AnswerEdge { int from, to; };
struct ContextLink { int position; double score; };

// The viewer constructs this object only in response to the Answer path switch.
struct AnswerPath {
    BranchView branches = BranchView::attention;
    std::vector<AnswerEdge> edges;
    std::vector<ContextLink> links;
    int origin = -1;
    bool available = false;

    void update(const Trace& trace, int frame, int layer, int head);
private:
    int last_frame = -1, last_layer = -1, last_head = -1;
    BranchView last_branches = BranchView::none;
};

struct ReplyText {
    std::string answer, tagged_thinking;
    bool in_thinking = false, saw_thinking = false;
    bool update(const Trace& trace, bool thinking_text, int visible_frames = -1);
private:
    int last_size = -1;
    bool last_finished = false, last_thinking = false;
};
