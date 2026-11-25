#pragma once
#include "pca.hpp"
#include "windows_utf.hpp"
#include <fstream>

struct Candidate {
    int id{}; std::string text; double p{}, draw{}, logit{};
};
struct LayerPoint { int layer; Point xyz; };
struct Frame {
    int index{}, id{}; std::string text, bytes, phase, decision;
    Point xyz{}; double ms{}, entropy{};
    std::vector<Candidate> top; Candidate next; bool has_next{};
    std::vector<Vector> attention; std::vector<LayerPoint> path; Vector embedding;
    std::vector<std::vector<Vector>> other_attention;
    const std::vector<Vector>& weights(int layer,int primary) const {
        static const std::vector<Vector> empty;
        if(layer==primary) return attention;
        return layer>=0 && size_t(layer)<other_attention.size()?other_attention[layer]:empty;
    }
};
struct Trace {
    std::string model, prompt, mode, reason;
    int dims{}, layers{}, heads{}, layer{-1}, prompt_tokens{}, fit{}, gpu{-1}, seed{};
    double temperature{}; Point variance{};
    bool finished{}, header{}, all_layers{};
    std::vector<Frame> frames;
    void line(const std::string& row);
    void open(const std::filesystem::path& path);
};
struct Session {
    Trace trace; std::filesystem::path source, scratch, log;
    std::string status; HANDLE worker{}; uintmax_t offset{}; std::string fragment;
    ~Session();
    void start(const std::vector<std::string>& options);
    void cancel();
    void poll();
    void replay(const std::filesystem::path& file);
};
std::filesystem::path file_dialog(bool save, bool model=false);
std::string label(const std::string& s);
