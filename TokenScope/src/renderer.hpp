#pragma once
#include "answer.hpp"
#include <memory>
struct Viewport { float x,y,w,h,sx,sy,screen_h; };
struct Camera {
    float yaw=.20f,pitch=.12f,distance=8.0f;
    Point target{};
    void focus_token(const Trace& trace, int index);
    void zoom(float wheel, bool cosmos);
};
struct Mark {
    float x,y; int index; std::string text; int priority;
    bool active; float r,g,b;
    int layer=-1;
};
struct RenderOptions {
    int scene=0, head=0, layer=0, frame=0; bool layer_path=true, draw_probs=false, effects=true;
    bool show_prompt=true, show_generated=true;
    bool token_visible(const Frame& f) const { return f.phase=="prompt"?show_prompt:show_generated; }
    float time=0, arrival=1;
};
class Renderer {
    struct Data;
    std::unique_ptr<Data> d;
public:
    Renderer(); ~Renderer();
    bool compute() const;
    std::vector<Mark> draw(const Trace&,const Viewport&,const Camera&,const RenderOptions&,const AnswerPath* = nullptr);
};
