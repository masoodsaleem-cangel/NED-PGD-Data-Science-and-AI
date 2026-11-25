#include <glad/glad.h>
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include "renderer.hpp"
#include <algorithm>
#include <cstdio>
#include <iostream>
#include <numeric>
#include <optional>

namespace fs=std::filesystem;
constexpr ImVec4 ink{.88f,.92f,.97f,1}, muted{.55f,.64f,.72f,1}, teal{.33f,.88f,.80f,1}, amber{1.f,.72f,.39f,1};
constexpr ImVec4 question_green{.43f,.91f,.57f,1}, answer_red{1.f,.44f,.47f,1};
constexpr ImGuiWindowFlags strip=ImGuiWindowFlags_NoTitleBar|ImGuiWindowFlags_NoResize|ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoSavedSettings|ImGuiWindowFlags_NoCollapse;
struct Fonts { ImFont *body,*bold,*title,*mono; };
static Fonts style() {
    ImGui::StyleColorsDark(); auto& s=ImGui::GetStyle();
    s.WindowRounding=0;s.ChildRounding=5;s.FrameRounding=5;s.GrabRounding=5;s.PopupRounding=8;
    s.WindowBorderSize=0;s.PopupBorderSize=1;s.FramePadding={9,5};s.ItemSpacing={7,6};
    auto col=[&](int i,float r,float g,float b,float a=1.f){s.Colors[i]={r,g,b,a};};
    col(ImGuiCol_WindowBg,.040f,.055f,.084f);col(ImGuiCol_PopupBg,.056f,.078f,.109f);
    col(ImGuiCol_Border,.16f,.22f,.28f);col(ImGuiCol_FrameBg,.083f,.113f,.151f);
    col(ImGuiCol_FrameBgHovered,.11f,.18f,.23f);col(ImGuiCol_FrameBgActive,.13f,.23f,.24f);
    col(ImGuiCol_Button,.091f,.128f,.170f);col(ImGuiCol_ButtonHovered,.13f,.22f,.25f);
    col(ImGuiCol_ButtonActive,.12f,.31f,.30f);col(ImGuiCol_SliderGrab,.26f,.67f,.61f);
    col(ImGuiCol_SliderGrabActive,.42f,.92f,.80f);s.Colors[ImGuiCol_CheckMark]=teal;
    s.Colors[ImGuiCol_Text]=ink;s.Colors[ImGuiCol_TextDisabled]=muted;
    col(ImGuiCol_Separator,.15f,.20f,.25f);
    ImGuiIO& io=ImGui::GetIO();io.IniFilename=nullptr;
    auto font=[&](const char* file,float size){
        auto path=fs::path(L"C:\\Windows\\Fonts")/file;
        if(fs::exists(path)) return io.Fonts->AddFontFromFileTTF(path.string().c_str(),size,nullptr,io.Fonts->GetGlyphRangesDefault());
        return io.Fonts->AddFontDefault();
    };
    return {font("segoeui.ttf",16),font("segoeuib.ttf",16),font("segoeuil.ttf",31),font("consola.ttf",14)};
}
struct Setup {
    std::string model; char prompt[8192]="The cheque is cashed at the";
    int tokens=32,seed=42,layer=-1,gpu=99,assistant_prefix=0;float temp=1.f;
    bool chat=false,attention=true,paths=true,raw=true,all=false;
    std::vector<std::string> args() const {
        std::vector<std::string> a={"--model",model,"--prompt",prompt,"--tokens",std::to_string(tokens),"--seed",std::to_string(seed),
            "--temperature",std::to_string(temp),"--layer",std::to_string(layer),"--gpu-layers",std::to_string(gpu)};
        if(chat)a.push_back("--chat");if(!attention)a.push_back("--no-attention");if(!paths)a.push_back("--no-paths");
        if(chat && assistant_prefix==1)a.push_back("--model-thinking");
        if(chat && assistant_prefix==2)a.push_back("--direct-answer");
        if(raw)a.push_back("--raw");if(attention && all)a.push_back("--all-layers");return a;
    }
};
struct State {
    Session session; Setup setup; RenderOptions view; Camera cameras[3]={{.18f,.15f,7.8f},{.15f,.18f,7.8f},{.24f,.17f,7.4f}};
    bool playing=false,inspector=true,labels=true,follow=false,settings=false,tour=false,focus=false;
    bool thinking_text=false,replay_response=false;
    std::optional<AnswerPath> answer_path;
    ReplyText reply;
    float speed=.79f; double changed=0,tick=0,tour_start=0; std::string message;
    void seek(int i,double now) {view.frame=std::clamp(i,0,std::max(0,int(session.trace.frames.size())-1));changed=now;tick=now;}
    void timeline_seek(int i,double now) {
        follow=tour=playing=false;
        replay_response=session.trace.finished;
        seek(i,now);
    }
    void toggle_playback(double now) {
        const auto& tr=session.trace;
        if(tr.frames.empty())return;
        follow=tour=false;
        playing=!playing;
        replay_response=tr.finished;
        if(playing && view.frame==int(tr.frames.size())-1)seek(tr.prompt_tokens-1,now);
        tick=now;
    }
    void reset_answer_views() {
        answer_path.reset();
        thinking_text=replay_response=false;
        cameras[0]={.18f,.15f,7.8f};
        reply=ReplyText{};
    }
    void toggle_path(double now) {
        if(answer_path) {answer_path.reset();return;}
        answer_path.emplace();
        view.scene=0;
        tour=false;
        const auto& tr=session.trace;
        if(view.frame<tr.prompt_tokens && int(tr.frames.size())>tr.prompt_tokens)
            seek(tr.prompt_tokens,now);
    }
    const AnswerPath* current_path() {
        if(!answer_path || view.scene!=0 || !view.show_generated || session.trace.frames.empty())return nullptr;
        answer_path->update(session.trace,view.frame,view.layer,view.head);
        return &*answer_path;
    }
    void load(const fs::path& p,double now) {
        session.replay(p);view.layer=std::max(0,session.trace.layer);view.head=0;follow=false;playing=tour=false;
        reset_answer_views();seek(session.trace.prompt_tokens-1,now);message.clear();
    }
    void start(double now) {
        session.start(setup.args());playing=tour=false;follow=true;view.head=0;view.layer=std::max(0,setup.layer);reset_answer_views();seek(0,now);message.clear();
    }
};
static void place(const char* name,float x,float y,float w,float h,ImGuiWindowFlags more=0) {
    ImGui::SetNextWindowPos({x,y});ImGui::SetNextWindowSize({w,h});ImGui::Begin(name,nullptr,strip|more);
}
static void caption(const char* text) {ImGui::TextColored(muted,"%s",text);}
static void section(const char* text) {ImGui::Spacing();ImGui::Separator();ImGui::Spacing();caption(text);}
static std::string short_model(std::string s) {
    if(s.size()>5 && s.substr(s.size()-5)==".gguf") s.resize(s.size()-5);
    return s;
}
static void toolbar(State& s,const Fonts& fonts,float w,double now) {
    place("##nav",0,0,w,43,ImGuiWindowFlags_NoScrollbar);
    ImGui::PushFont(fonts.bold);ImGui::TextColored(teal,"TokenScope");ImGui::PopFont();
    const char* tabs[]={"Cosmos","Loom","Race"};
    for(int n=0;n<3;++n){
        ImGui::SameLine(0,n==0?22.f:4.f);
        if(s.view.scene==n) ImGui::PushStyleColor(ImGuiCol_Button,ImVec4{.105f,.255f,.255f,1});
        bool click=ImGui::Button(tabs[n]);if(s.view.scene==n)ImGui::PopStyleColor();
        if(click){s.view.scene=n;s.tour=false;}
    }
    if(w>825){
        ImGui::SameLine(0,16);bool live=s.session.worker!=nullptr;
        auto p=ImGui::GetCursorScreenPos();ImGui::GetWindowDrawList()->AddRectFilled({p.x,p.y+7},{p.x+7,p.y+14},live?IM_COL32(91,220,133,255):IM_COL32(135,160,179,255),1);
        ImGui::Dummy({8,18});ImGui::SameLine(0,4);ImGui::TextColored(muted,"%s",live?"LIVE":"REPLAY");
    }
    ImGui::SameLine(std::max(ImGui::GetCursorPosX()+8,w-353));
    ImGui::BeginDisabled(s.session.trace.frames.empty()||s.session.worker);
    if(ImGui::Button(s.tour?"End tour":"Tour")){s.tour=!s.tour;s.playing=s.follow=false;s.tour_start=now;}
    ImGui::EndDisabled();ImGui::SameLine();
    if(ImGui::Button("New run"))s.settings=true;ImGui::SameLine();
    if(ImGui::Button("Open")){auto p=file_dialog(false);if(!p.empty()){try{s.load(p,now);}catch(const std::exception& e){s.message=e.what();}}}
    ImGui::SameLine();ImGui::BeginDisabled(!s.session.trace.finished);
    if(ImGui::Button("Save")){auto p=file_dialog(true);if(!p.empty()){try{
        std::error_code ec;if(!fs::equivalent(s.session.source,p,ec))fs::copy_file(s.session.source,p,fs::copy_options::overwrite_existing);
        s.message="Saved "+p.filename().u8string();}catch(const std::exception& e){s.message=e.what();}}}
    ImGui::EndDisabled();ImGui::SameLine();if(ImGui::Button("Inspect"))s.inspector=!s.inspector;
    ImGui::End();
}
static void run_dialog(State& s,double now) {
    if(s.settings){ImGui::OpenPopup("New generation");s.settings=false;}
    ImGui::SetNextWindowSize({486,0},ImGuiCond_Appearing);
    bool opened=true;
    if(!ImGui::BeginPopupModal("New generation",&opened,ImGuiWindowFlags_AlwaysAutoResize))return;
    auto& u=s.setup;
    ImGui::TextWrapped("%s",u.model.empty()?"Choose a local GGUF model.":u.model.c_str());
    if(ImGui::Button("Choose GGUF...")){auto p=file_dialog(false,true);if(!p.empty())u.model=p.u8string();}
    const fs::path qwen=L"C:\\qwen2.5-0.5b-instruct-q4_k_m.gguf";
    const fs::path ornith=L"C:\\Ornith AI - 1.0-9b-Q4_K_M\\ornith-1.0-9b-Q4_K_M.gguf";
    if(fs::exists(qwen)){ImGui::SameLine();if(ImGui::Button("Qwen 0.5B"))u.model=qwen.u8string();}
    if(fs::exists(ornith)){ImGui::SameLine();if(ImGui::Button("Ornith 9B"))u.model=ornith.u8string();}
    section("PROMPT");ImGui::InputTextMultiline("##prompt",u.prompt,sizeof(u.prompt),{-1,67});
    int input_mode=u.chat?1:0;
    const char* modes[]={"Raw text","Chat (one user turn)"};
    ImGui::SetNextItemWidth(224);
    if(ImGui::Combo("Input format",&input_mode,modes,2))u.chat=input_mode==1;
    ImGui::SetItemTooltip("Raw text uses your prompt and any start token required by the tokenizer. Chat adds the model's turn markers.");
    if(u.chat){
        const char* prefixes[]={"None","Open thinking block","Empty thinking block"};
        ImGui::SetNextItemWidth(224);ImGui::Combo("Assistant prefix",&u.assistant_prefix,prefixes,3);
        ImGui::SetItemTooltip("None starts at the assistant turn. Ornith supports an optional open or empty <think> block.");
    }
    ImGui::SetNextItemWidth(224);ImGui::SliderInt("New tokens",&u.tokens,0,256);
    ImGui::SetNextItemWidth(224);ImGui::SliderFloat("Temperature",&u.temp,0,2,"%.2f");
    ImGui::SetItemTooltip("1 samples the model's original probabilities. 0 always picks the highest-scoring next token.");
    ImGui::SetNextItemWidth(224);ImGui::InputInt("Seed",&u.seed);u.seed=std::max(0,u.seed);
    ImGui::SetNextItemWidth(224);ImGui::SliderInt("GPU layers",&u.gpu,0,99);
    ImGui::Checkbox("Attention",&u.attention);ImGui::SameLine();ImGui::Checkbox("Layer paths",&u.paths);ImGui::SameLine();ImGui::Checkbox("Raw vectors",&u.raw);
    if(u.attention){
        ImGui::Checkbox("Record all layers",&u.all);
        if(u.all)caption("Up to 96 positions, including chat formatting and new tokens.");
        else {ImGui::SetNextItemWidth(150);ImGui::InputInt("Attention layer",&u.layer);u.layer=std::clamp(u.layer,-1,2047);ImGui::SameLine();caption("-1 = middle");}
    }
    ImGui::Spacing();ImGui::BeginDisabled(u.model.empty() || u.prompt[0]==0);
    if(ImGui::Button("Generate",{120,0})){try{s.start(now);ImGui::CloseCurrentPopup();}catch(const std::exception& e){s.message=e.what();}}
    ImGui::EndDisabled();ImGui::SameLine();if(ImGui::Button("Close"))ImGui::CloseCurrentPopup();
    ImGui::EndPopup();
}
static bool switch_button(const char* label,bool on) {
    const float height=ImGui::GetFrameHeight();
    const float track=27;
    const ImVec2 p=ImGui::GetCursorScreenPos();
    const ImVec2 text_size=ImGui::CalcTextSize(label);
    const bool click=ImGui::InvisibleButton(label,{track+6+text_size.x,height},ImGuiButtonFlags_EnableNav);
    bool shown_on=click?!on:on;
    auto* draw=ImGui::GetWindowDrawList();
    const float mid=p.y+height*.5f;
    draw->AddRectFilled({p.x,mid-7},{p.x+track,mid+7},shown_on?IM_COL32(48,133,105,255):IM_COL32(56,68,83,255),7);
    draw->AddCircleFilled({p.x+(shown_on?track-7:7),mid},4.8f,shown_on?IM_COL32(194,255,216,255):IM_COL32(182,189,200,255));
    draw->AddText({p.x+track+6,mid-text_size.y*.5f},ImGui::GetColorU32(ImGuiCol_Text),label);
    if(ImGui::IsItemFocused())draw->AddRect(p,{p.x+track+6+text_size.x,p.y+height},IM_COL32(91,187,171,255),3);
    return click;
}
static void colored_line(const char* name,const std::string& value,const ImVec4& color) {
    auto first=value.find_first_not_of(" \r\n\t");
    ImGui::PushStyleColor(ImGuiCol_Text,color);
    ImGui::TextWrapped("%s %s",name,first==std::string::npos?"":value.c_str()+first);
    ImGui::PopStyleColor();
}
static void legend_led(const char* name,bool& visible,ImU32 light,const char* hint) {
    const ImVec2 pos=ImGui::GetCursorScreenPos();
    const auto text=ImGui::CalcTextSize(name);
    const float h=24, w=text.x+26;
    if(ImGui::InvisibleButton(name,{w,h},ImGuiButtonFlags_EnableNav))visible=!visible;
    auto* draw=ImGui::GetWindowDrawList();
    ImVec2 bulb{pos.x+5,pos.y+(h-9)*.5f};
    if(visible){
        draw->AddRectFilled({bulb.x-2,bulb.y-2},{bulb.x+11,bulb.y+11},(light&0x00ffffffu)|(46u<<24),3);
        draw->AddRectFilled(bulb,{bulb.x+9,bulb.y+9},light,2);
    } else {
        draw->AddRect(bulb,{bulb.x+9,bulb.y+9},IM_COL32(111,123,137,255),2);
    }
    draw->AddText({pos.x+20,pos.y+(h-text.y)*.5f},visible?IM_COL32(239,214,143,255):IM_COL32(142,152,165,255),name);
    if(ImGui::IsItemHovered() || ImGui::IsItemFocused())
        draw->AddRect(pos,{pos.x+w,pos.y+h},IM_COL32(82,102,119,255),4);
    ImGui::SetItemTooltip("%s  |  %s",visible?"On":"Off",hint);
}
static bool cosmos_legend(State& s,const Viewport& view) {
    if(s.view.scene!=0)return false;
    ImGui::SetNextWindowPos({view.x+10,view.y+view.h-37});
    ImGui::SetNextWindowBgAlpha(.89f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding,{5,3});
    ImGui::PushStyleVar(ImGuiStyleVar_WindowMinSize,{1,1});
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding,5);
    ImGui::Begin("##cosmos_leds",nullptr,strip|ImGuiWindowFlags_AlwaysAutoResize|ImGuiWindowFlags_NoFocusOnAppearing|ImGuiWindowFlags_NoScrollbar);
    legend_led("Prompt",s.view.show_prompt,IM_COL32(66,224,203,255),"Prompt tokens and their links");
    ImGui::SameLine(0,6);
    legend_led("Generated",s.view.show_generated,IM_COL32(255,169,76,255),"Generated tokens and their links");
    ImGui::SameLine(0,6);
    legend_led("Layer path",s.view.layer_path,IM_COL32(179,144,255,255),
               "One token through the model's layers. Hover a violet dot for its layer number.\nLoom shows attention between tokens.");
    bool hovered=ImGui::IsWindowHovered();
    ImGui::End();ImGui::PopStyleVar(3);
    return hovered;
}
static void footer(State& s,const Fonts& fonts,float w,float h,float height,double now) {
    auto& tr=s.session.trace;int count=int(tr.frames.size());
    place("##timeline",0,h-height,w,height);
    ImGui::BeginDisabled(!count);
    if(ImGui::Button(s.playing?"Pause":"Play",{62,0}))s.toggle_playback(now);
    ImGui::SameLine();if(ImGui::Button("<"))s.timeline_seek(s.view.frame-1,now);
    ImGui::SameLine();if(ImGui::Button(">"))s.timeline_seek(s.view.frame+1,now);
    ImGui::SameLine();int index=s.view.frame+1;
    const float reserved=w>=850?480.f:393.f;
    ImGui::SetNextItemWidth(std::max(45.f,w-reserved-(s.session.worker?62.f:0.f)));
    if(ImGui::SliderInt("##frame",&index,1,std::max(1,count),"%d"))s.timeline_seek(index-1,now);
    ImGui::SameLine();ImGui::TextColored(muted,"/ %d",count);
    if(w>=850){ImGui::SameLine();ImGui::SetNextItemWidth(65);ImGui::SliderFloat("##step",&s.speed,.12f,2.f,"%.2fs");}
    ImGui::EndDisabled();
    if(s.session.worker){ImGui::SameLine();if(ImGui::SmallButton(s.follow?"Stop":"Follow")){if(s.follow)s.session.cancel();else s.follow=true;}}
    ImGui::SameLine();
    if(switch_button("Answer path",s.answer_path.has_value()))s.toggle_path(now);
    ImGui::SetItemTooltip("Build the generated token path in Cosmos. Switching off releases the path.");
    ImGui::SameLine();
    if(switch_button("Thinking text",s.thinking_text))s.thinking_text=!s.thinking_text;
    ImGui::SetItemTooltip("Show the selected token step and any thinking text explicitly emitted by the model.");
    ImGui::BeginChild("##response",{0,0});
    const bool at_bottom=ImGui::GetScrollY()>=ImGui::GetScrollMaxY()-1.f;
    if(!s.message.empty())ImGui::TextWrapped("%s",s.message.c_str());
    if(!s.session.worker && !tr.finished && !s.session.status.empty())ImGui::TextColored(amber,"%s",s.session.status.c_str());
    const int visible=s.replay_response && tr.finished?std::min(count,s.view.frame+1):count;
    const bool complete=tr.finished && visible==count;
    const bool changed=s.reply.update(tr,s.thinking_text,visible);
    const std::string question=tr.header?tr.prompt:(!s.session.source.empty()?s.setup.prompt:"");
    if(!question.empty()) {
        colored_line("Question:",question,question_green);
        colored_line("Answer:",s.reply.answer,answer_red);
        const bool empty=s.reply.answer.find_first_not_of(" \r\n\t")==std::string::npos;
        const char* status=nullptr;
        if(complete && tr.reason=="limit"){
            if(count<=tr.prompt_tokens)status="Prompt only. The generation budget was zero.";
            else if(empty && s.reply.in_thinking)status="Token limit reached during model thinking, before a final answer.";
            else if(empty && s.reply.saw_thinking)status="Token limit reached after thinking, before a final answer.";
            else status=empty?"Token limit reached before a visible answer.":"Token limit reached.";
        } else if(complete && empty)status="The model ended this reply without a visible answer.";
        else if(empty && (s.session.worker || s.replay_response)){
            if(!tr.header)status="Loading the model and reading the prompt...";
            else if(visible<tr.prompt_tokens)status="Reading the prompt...";
            else if(s.reply.in_thinking)status="Model is generating thinking text...";
            else status="Waiting for the first answer token...";
        }
        if(status){
            if(empty)ImGui::SameLine();
            ImGui::PushStyleColor(ImGuiCol_Text,muted);ImGui::TextWrapped("%s",status);ImGui::PopStyleColor();
        }
    }
    if(s.thinking_text && count>0) {
        const auto& f=tr.frames[s.view.frame];
        ImGui::PushFont(fonts.mono);
        if(f.has_next) {
            const char* action=f.decision=="prompt"?"next supplied":f.decision=="eog"?"end token":"sampled";
            ImGui::TextWrapped("Step %d   %s   %s %s   (model %.2f%%)",s.view.frame+1,label(f.text).c_str(),
                               action,label(f.next.text).c_str(),100*f.next.p);
        } else ImGui::TextWrapped("Step %d   %s   End of recorded generation",s.view.frame+1,label(f.text).c_str());
        ImGui::PopFont();
        if(!s.reply.tagged_thinking.empty())colored_line("Model thinking:",s.reply.tagged_thinking,muted);
    }
    if(changed && at_bottom && (s.session.worker || s.follow || s.playing))ImGui::SetScrollHereY(1.f);
    ImGui::EndChild();ImGui::End();
}
static void inspector(State& s,const Fonts& fonts,float x,float y,float w,float h,double now) {
    place("##inspector",x,y,w,h);
    auto& tr=s.session.trace;
    caption(tr.header?"MODEL":"CAPTURE");ImGui::TextWrapped("%s",tr.header?short_model(tr.model).c_str():s.session.status.c_str());
    if(!tr.header || tr.frames.empty()){ImGui::End();return;}
    ImGui::PushFont(fonts.mono);ImGui::TextColored(muted,"%d dims   %d layers   %d heads",tr.dims,tr.layers,tr.heads);ImGui::PopFont();
    ImGui::TextColored(tr.gpu>0?teal:muted,"%s",tr.gpu>0?("GPU  /  "+std::to_string(tr.gpu)+" layers offloaded").c_str():(tr.gpu==0?"CPU inference":"Device unreported"));
    if(ImGui::TreeNode("Model input")){
        std::string input,ids;
        int recorded=0;
        for(const auto& f:tr.frames){
            if(f.phase!="prompt")break;
            input+=f.bytes;
            if(recorded++)ids+=' ';
            ids+=std::to_string(f.id);
        }
        ImGui::TextColored(muted,"%s   %d/%d input tokens",tr.mode=="chat"?"Chat":"Raw text",recorded,tr.prompt_tokens);
        ImGui::TextColored(muted,"Temperature %.2f   seed %d",tr.temperature,tr.seed);
        ImGui::PushFont(fonts.mono);ImGui::TextWrapped("%s",input.c_str());ImGui::PopFont();
        if(ImGui::SmallButton("Copy input"))ImGui::SetClipboardText(input.c_str());
        if(ImGui::TreeNode("Token IDs")){ImGui::TextWrapped("%s",ids.c_str());ImGui::TreePop();}
        ImGui::TreePop();
    }
    const auto& f=tr.frames[s.view.frame];section("TOKEN");
    ImGui::PushFont(fonts.bold);ImGui::TextWrapped("%s",label(f.text).c_str());ImGui::PopFont();
    ImGui::PushFont(fonts.mono);ImGui::TextColored(muted,"ID %d    %s",f.id,f.phase.c_str());ImGui::PopFont();
    ImGui::Text("Entropy     %.2f bits",f.entropy);
    ImGui::SetItemTooltip("How spread out the next-token probabilities are, before sampling temperature.\nOne certain token = 0 bits. Two equally likely tokens = 1 bit.");
    ImGui::Text("Decode      %.1f ms",f.ms);
    if(s.view.scene==0) {
        if(s.answer_path) {
            auto& path=*s.answer_path;
            section("ANSWER PATH");
            int mode=static_cast<int>(path.branches);
            const char* choices[]={"Attention","Similar tokens","None"};
            ImGui::SetNextItemWidth(w-92);
            if(ImGui::Combo("Branches",&mode,choices,3))path.branches=static_cast<BranchView>(mode);
            if(path.branches==BranchView::attention && tr.layer>=0) {
                if(tr.all_layers){ImGui::SetNextItemWidth(w-68);ImGui::SliderInt("Layer",&s.view.layer,0,tr.layers-1);}
                else ImGui::TextColored(muted,"Recorded layer %d",tr.layer);
                ImGui::SetNextItemWidth(w-68);ImGui::SliderInt("Head",&s.view.head,0,tr.heads-1);
            }
            s.current_path();
            if(!s.view.show_generated)caption("Enable the Generated LED to view.");
            else if(f.phase!="generated") {
                if(tr.finished && int(tr.frames.size())<=tr.prompt_tokens)caption("No generated tokens in this run.");
                else caption("The path begins at the first draw.");
            } else if(path.branches!=BranchView::none) {
                if(!path.available)ImGui::TextWrapped("%s",path.branches==BranchView::similar?
                    "Full vectors are unavailable for this comparison.":"No attention row for this prediction.");
                else {
                    bool weights=path.branches==BranchView::attention;
                    ImGui::TextWrapped("%s #%d  %s",weights?"Predicting query":"Comparing token",path.origin+1,label(tr.frames[path.origin].text).c_str());
                    for(const auto& link:path.links) {
                        std::string piece=label(tr.frames[link.position].text);
                        if(weights)ImGui::Text("  #%d  %s    %.1f%%",link.position+1,piece.c_str(),100*link.score);
                        else ImGui::Text("  #%d  %s    cos %.3f",link.position+1,piece.c_str(),link.score);
                    }
                }
            }
        }
        section("PROJECTION");ImGui::Text("3 PCs retain %.1f%%",100*(tr.variance[0]+tr.variance[1]+tr.variance[2]));
        ImGui::TextColored(muted,"Basis fixed on %d tokens",tr.fit);
        if(s.view.layer_path)ImGui::TextColored(muted,"This token across %d of %d layers",int(f.path.size()),tr.layers);
        int twin=-1;for(int j=s.view.frame-1;j>=0;--j)if(tr.frames[j].id==f.id){twin=j;break;}
        if(twin>=0 && !f.embedding.empty() && tr.frames[twin].embedding.size()==f.embedding.size()){
            Vector a=unit(f.embedding),b=unit(tr.frames[twin].embedding);
            double sim=std::inner_product(a.begin(),a.end(),b.begin(),0.);
            section("SAME TOKEN, EARLIER CONTEXT");ImGui::Text("Cosine similarity   %.3f",sim);
            if(ImGui::SmallButton(("Go to position "+std::to_string(twin+1)).c_str())){s.follow=s.tour=s.playing=false;s.seek(twin,now);}
        }
    } else if(s.view.scene==1) {
        section("ATTENTION");
        if(tr.all_layers){ImGui::SetNextItemWidth(w-68);ImGui::SliderInt("Layer",&s.view.layer,0,tr.layers-1);}
        else if(tr.layer>=0)ImGui::Text("Recorded layer   %d",tr.layer);
        ImGui::SetNextItemWidth(w-68);ImGui::SliderInt("Head",&s.view.head,0,tr.heads-1);
        const auto& rows=f.weights(s.view.layer,tr.layer);
        if(rows.empty()){ImGui::TextWrapped("No measured attention row at this layer and step.");}
        else {
            const auto& a=rows.at(s.view.head);auto strongest=std::max_element(a.begin(),a.end());int k=int(strongest-a.begin());
            ImGui::Text("Strongest key   #%d",k+1);
            ImGui::TextColored(teal,"%s    %.1f%%",label(tr.frames[k].text).c_str(),100.*(*strongest));
            ImGui::TextColored(muted,"Up to 12 strongest links shown");
        }
    } else {
        section("DISTRIBUTION");ImGui::Checkbox("Apply sampling temperature",&s.view.draw_probs);
        ImGui::TextColored(muted,"T %.2f    seed %d",tr.temperature,tr.seed);
    }
    section("NEXT TOKEN");
    for(size_t j=0;j<f.top.size();++j){
        const auto& v=f.top[j]; bool selected=f.has_next&&v.id==f.next.id;double p=(s.view.scene==2&&s.view.draw_probs)?v.draw:v.p;
        auto start=ImGui::GetCursorScreenPos();float width=ImGui::GetContentRegionAvail().x;
        ImGui::GetWindowDrawList()->AddRectFilled({start.x,start.y+18},{start.x+float(p)*width,start.y+20},selected?IM_COL32(241,169,85,230):IM_COL32(65,179,169,220));
        std::string nm=label(v.text);ImGui::TextColored(selected?amber:ink,"%s",nm.c_str());
        ImGui::SameLine(std::max(100.f,w-78));ImGui::Text("%.2f%%",p*100);ImGui::Dummy({0,1});
    }
    if(f.has_next){caption(f.decision=="prompt"?"Next prompt token":(f.decision=="eog"?"End of generation":"Sampled token"));ImGui::TextColored(amber,"%s",label(f.next.text).c_str());}
    ImGui::End();
}
static void overlay(State& s,const Fonts& fonts,const Viewport& v,std::vector<Mark> marks,double now,bool over_legend) {
    auto* d=ImGui::GetBackgroundDrawList();d->PushClipRect({v.x,v.y},{v.x+v.w,v.y+v.h},true);
    const char* titles[]={"Embedding Cosmos","Attention Loom","Logit Race"};
    const char* subs[]={"Double-click a word to focus. Scroll to zoom. Home for the origin.","Attention from the current query to earlier keys and itself","Top five next tokens by probability"};
    d->AddText(fonts.title,31,{v.x+19,v.y+11},IM_COL32(228,240,247,255),titles[s.view.scene]);
    d->AddText(fonts.body,16,{v.x+21,v.y+48},IM_COL32(144,168,183,255),subs[s.view.scene]);
    const auto& tr=s.session.trace;
    if(!tr.frames.empty() && s.view.scene==1 && tr.frames[s.view.frame].weights(s.view.layer,tr.layer).empty())
        d->AddText(fonts.body,16,{v.x+21,v.y+84},IM_COL32(252,195,121,255),"No attention row recorded for this layer and token.");
    if(tr.frames.empty())d->AddText(fonts.body,16,{v.x+21,v.y+86},IM_COL32(134,212,199,255),s.session.status.c_str());
    std::stable_sort(marks.begin(),marks.end(),[](auto& a,auto& b){return a.priority>b.priority;});
    ImVec2 mouse=ImGui::GetIO().MousePos;bool canvas=mouse.x>v.x && mouse.x<v.x+v.w && mouse.y>v.y && mouse.y<v.y+v.h && !over_legend && !ImGui::GetIO().WantCaptureMouse;
    std::vector<ImVec4> used;
    int hovered=-1,clicked=-1;float best=18*18;
    const Mark* layer_dot=nullptr;float layer_dist=6*6;
    for(size_t i=0;i<marks.size();++i){
        const auto& m=marks[i];
        float dx=mouse.x-m.x,dy=mouse.y-m.y,dist=dx*dx+dy*dy;
        if(m.layer>=0){
            if(dist<layer_dist){layer_dist=dist;layer_dot=&m;}
        }else if(dist<best){best=dist;hovered=int(i);}
    }
    if(canvas && layer_dot && layer_dist<best){
        d->AddCircle({layer_dot->x,layer_dot->y},4.f,IM_COL32(190,161,244,225),16,1.f);
        ImGui::SetTooltip("Token \"%s\"  |  Layer %d",label(tr.frames[s.view.frame].text).c_str(),layer_dot->layer);
    }
    for(size_t j=0;j<marks.size();++j){
        const auto& m=marks[j];if(m.layer>=0 || m.x<v.x+3||m.x>v.x+v.w-4||m.y<v.y+5||m.y>v.y+v.h-10)continue;
        bool hot=canvas && int(j)==hovered;
        if(hot && m.index>=0 && ImGui::IsMouseClicked(ImGuiMouseButton_Left))clicked=m.index;
        ImU32 color=ImGui::ColorConvertFloat4ToU32({m.r,m.g,m.b,1});
        if(m.active)d->AddCircle({m.x,m.y},10,color,36,1.4f);
        if((!s.labels && !m.active && !hot) || (m.priority<12 && !hot))continue;
        std::string text=m.text; auto size=fonts.mono->CalcTextSizeA(14,320,0,text.c_str());
        float x=std::clamp(m.x+9,v.x+3,std::max(v.x+3,v.x+v.w-size.x-12)),y=m.y-19;
        if(s.view.scene==2){x=std::clamp(m.x-size.x*.5f,v.x+3,std::max(v.x+3,v.x+v.w-size.x-12));y=m.y-23;}
        ImVec4 box{x-3,y-2,x+size.x+5,y+size.y+3};
        bool overlaps=false;for(auto a:used)if(box.x<a.z && box.z>a.x && box.y<a.w && box.w>a.y){overlaps=true;break;}
        if((overlaps || y<v.y+70) && !hot)continue;
        if(canvas && clicked<0 && m.index>=0 && mouse.x>=box.x && mouse.x<=box.z && mouse.y>=box.y && mouse.y<=box.w &&
           ImGui::IsMouseClicked(ImGuiMouseButton_Left))clicked=m.index;
        used.push_back(box);d->AddRectFilled({box.x,box.y},{box.z,box.w},IM_COL32(11,21,33,191),3);
        d->AddText(fonts.mono,14,{x,y},m.active||hot?IM_COL32(254,238,200,255):IM_COL32(191,213,225,240),text.c_str());
    }
    if(clicked>=0){
        s.follow=s.tour=s.playing=false;s.seek(clicked,now);
        if(s.view.scene==0 && ImGui::IsMouseDoubleClicked(ImGuiMouseButton_Left))s.cameras[0].focus_token(tr,clicked);
    }
    if(s.view.scene!=0){
        const char* bottom=s.view.scene==1?"Amber  query     Ribbon width  attention weight":"Amber  selected token     Heights scaled to current leader";
        d->AddText(fonts.mono,14,{v.x+18,v.y+v.h-27},IM_COL32(142,172,186,255),bottom);
    }
    d->PopClipRect();
}
static void screenshot(const fs::path& path,int w,int h) {
    std::vector<unsigned char> p(size_t(w)*h*3);glPixelStorei(GL_PACK_ALIGNMENT,1);glReadBuffer(GL_BACK);
    glReadPixels(0,0,w,h,GL_RGB,GL_UNSIGNED_BYTE,p.data());
    std::ofstream out(path,std::ios::binary);if(!out)throw std::runtime_error("Cannot save snapshot");
    out<<"P6\n"<<w<<" "<<h<<"\n255\n";for(int y=h-1;y>=0;--y)out.write((char*)p.data()+size_t(y)*w*3,std::streamsize(w)*3);
}
static void guided_frame(State& s,double t) {
    const auto& tr=s.session.trace;
    if(tr.frames.empty())return;
    int end=std::min(tr.prompt_tokens,int(tr.frames.size()))-1;
    int repeat=end;
    // Give an identical token in different contexts a few seconds on screen.
    for(int i=end;i>0 && repeat==end;--i){
        if(tr.frames[i].text.size()<4)continue;
        for(int j=0;j<i;++j)if(tr.frames[j].id==tr.frames[i].id){repeat=i;break;}
    }
    float time=float(std::fmod(t,12.0));
    s.view.scene=int(time/4);float local=time-s.view.scene*4;
    if(s.view.scene==0) {
        s.view.frame=repeat;s.cameras[0]={.23f+.26f*std::sin(time*.7f),.21f,6.8f};
    } else if(s.view.scene==1) {
        s.view.frame=end;s.view.layer=std::max(0,tr.layer);s.view.head=std::min(3,tr.heads-1);
        s.cameras[1]={-.28f+.43f*std::sin(local*.62f),.22f,7.45f};
    } else {
        s.view.frame=std::min(int(tr.frames.size())-1,end+(local>3.0f?1:0));
        s.cameras[2]={.25f+.09f*std::sin(local*.8f),.17f,7.2f};
    }
    s.view.time=float(t);s.view.arrival=s.view.scene==2 && local>3.f?local-3.f:local;
}
static int run(const std::vector<std::string>& args) {
    State s;fs::path trace,snap,film;int target=-1,requested_layer=-1,requested_head=0;bool live=false,start_tour=false;
    const auto default_model=fs::path(L"C:\\qwen2.5-0.5b-instruct-q4_k_m.gguf");if(fs::exists(default_model))s.setup.model=default_model.u8string();
    for(size_t i=0;i<args.size();++i){
        auto a=args[i];auto val=[&](){if(++i>=args.size())throw std::runtime_error("Missing "+a);return args[i];};
        if(a=="--trace")trace=fs::u8path(val());else if(a=="--snapshot")snap=fs::u8path(val());
        else if(a=="--tour")start_tour=true;else if(a=="--film")film=fs::u8path(val());
        else if(a=="--scene")s.view.scene=std::clamp(std::stoi(val()),0,2);
        else if(a=="--frame")target=std::stoi(val());else if(a=="--head")requested_head=std::stoi(val());
        else if(a=="--layer")requested_layer=s.setup.layer=std::stoi(val());
        else if(a=="--model"){s.setup.model=val();live=true;}else if(a=="--tokens")s.setup.tokens=std::stoi(val());
        else if(a=="--gpu-layers")s.setup.gpu=std::stoi(val());else if(a=="--prompt"){auto v=val();if(v.size()>=sizeof(s.setup.prompt))throw std::runtime_error("Prompt too long");std::snprintf(s.setup.prompt,sizeof(s.setup.prompt),"%s",v.c_str());}
        else if(a=="--chat")s.setup.chat=true;else if(a=="--completion")s.setup.chat=false;
        else if(a=="--model-thinking" || a=="--direct-answer"){
            const int requested=a=="--model-thinking"?1:2;
            if(s.setup.assistant_prefix && s.setup.assistant_prefix!=requested)throw std::runtime_error("Choose only one assistant prefix.");
            s.setup.assistant_prefix=requested;
        }else if(a=="--all-layers")s.setup.all=true;
        else if(args.size()==1 && fs::u8path(a).extension()==".jsonl")trace=fs::u8path(a);
        else throw std::runtime_error("Unknown viewer argument: "+a);
    }
    if(!s.setup.chat && s.setup.assistant_prefix)throw std::runtime_error("An assistant prefix requires --chat.");
    SetProcessDPIAware();
    glfwSetErrorCallback([](int,const char* msg){std::cerr<<"GLFW: "<<msg<<'\n';});
    if(!glfwInit())throw std::runtime_error("Cannot initialize GLFW");
    struct EndGlfw{~EndGlfw(){glfwTerminate();}} endGlfw;
    const bool hidden=!snap.empty()||!film.empty();
    if(!film.empty() && (live || !snap.empty()))throw std::runtime_error("Film export requires a completed replay.");
    if(!film.empty() && !fs::create_directory(film))throw std::runtime_error("Choose a new directory for film frames.");
    int W=1220,H=740;
    if(!hidden){if(auto* monitor=glfwGetPrimaryMonitor()){int x,y,mw,mh;glfwGetMonitorWorkarea(monitor,&x,&y,&mw,&mh);W=std::min(W,mw-48);H=std::min(H,mh-65);}}
    glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,4);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,5);
    glfwWindowHint(GLFW_VISIBLE,hidden?GLFW_FALSE:GLFW_TRUE);glfwWindowHint(GLFW_SAMPLES,4);
    auto* window=glfwCreateWindow(W,H,"TokenScope  |  LLM Embedding Visualizer",nullptr,nullptr);
    if(!window){glfwWindowHint(GLFW_SAMPLES,0);window=glfwCreateWindow(W,H,"TokenScope  |  LLM Embedding Visualizer",nullptr,nullptr);}
    if(!window){glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);window=glfwCreateWindow(W,H,"TokenScope  |  LLM Embedding Visualizer",nullptr,nullptr);}
    if(!window)throw std::runtime_error("An OpenGL 3.3 or newer Windows display driver is required.");
    struct DropWindow{GLFWwindow* w;~DropWindow(){glfwDestroyWindow(w);}} dropWindow{window};
    glfwSetWindowSizeLimits(window,650,420,GLFW_DONT_CARE,GLFW_DONT_CARE);glfwMakeContextCurrent(window);glfwSwapInterval(hidden?0:1);
    if(!gladLoadGLLoader((GLADloadproc)glfwGetProcAddress))throw std::runtime_error("Cannot load OpenGL");
    IMGUI_CHECKVERSION();ImGui::CreateContext();Fonts fonts=style();
    ImGui_ImplGlfw_InitForOpenGL(window,true);
    if(!ImGui_ImplOpenGL3_Init("#version 330"))throw std::runtime_error("Cannot start the OpenGL interface");
    struct EndUI{~EndUI(){ImGui_ImplOpenGL3_Shutdown();ImGui_ImplGlfw_Shutdown();ImGui::DestroyContext();}} endUI;
    Renderer renderer;
    if(live)s.start(glfwGetTime());
    else {
        auto example=trace.empty()?application_dir()/"examples"/"two-banks.jsonl":trace;
        if(trace.empty() && !fs::exists(example))example=application_dir().parent_path()/"examples"/"two-banks.jsonl";
        if(fs::exists(example))s.load(example,glfwGetTime());
        else if(!trace.empty())throw std::runtime_error("Requested trace was not found");
        else s.session.status="Open a trace or start a new GGUF run.";
    }
    if(target>=0 && !live)s.seek(target,glfwGetTime());
    if(s.session.trace.header){s.view.head=std::clamp(requested_head,0,s.session.trace.heads-1);if(requested_layer>=0)s.view.layer=std::clamp(requested_layer,0,s.session.trace.layers-1);}
    s.changed=-2;s.inspector=W>=950;s.tour=start_tour||!film.empty();s.tour_start=glfwGetTime();
    if(!film.empty() && s.session.trace.frames.empty())throw std::runtime_error("A film requires a replay trace");
    int draws=0,film_frame=0;
    while(!glfwWindowShouldClose(window)){
        glfwPollEvents();double now=glfwGetTime();auto& tr=s.session.trace;bool had=tr.header;
        try{s.session.poll();}catch(const std::exception& e){s.session.cancel();s.message=e.what();}
        if(!had && tr.header) {s.view.layer=std::max(0,tr.layer);s.view.head=std::clamp(requested_head,0,tr.heads-1);}
        int count=int(tr.frames.size());
        if(s.follow && count>0 && s.view.frame!=count-1)s.seek(count-1,now);
        if(s.playing && count && now-s.tick>=s.speed){if(s.view.frame<count-1)s.seek(s.view.frame+1,now);else s.playing=false;}
        int fw,fh;glfwGetFramebufferSize(window,&fw,&fh);glfwGetWindowSize(window,&W,&H);
        if(fw<1||fh<1||W<1||H<1){glfwWaitEventsTimeout(.1);continue;}
        ImGui_ImplOpenGL3_NewFrame();ImGui_ImplGlfw_NewFrame();ImGui::NewFrame();
        auto& io=ImGui::GetIO();
        if(!io.WantTextInput && !ImGui::IsPopupOpen(nullptr,ImGuiPopupFlags_AnyPopupId)){
            if(ImGui::IsKeyPressed(ImGuiKey_Space))s.toggle_playback(now);
            if(ImGui::IsKeyPressed(ImGuiKey_RightArrow))s.timeline_seek(s.view.frame+1,now);
            if(ImGui::IsKeyPressed(ImGuiKey_LeftArrow))s.timeline_seek(s.view.frame-1,now);
            for(int i=0;i<3;++i)if(ImGui::IsKeyPressed((ImGuiKey)(ImGuiKey_1+i))){s.view.scene=i;s.tour=false;}
            if(ImGui::IsKeyPressed(ImGuiKey_Tab))s.focus=!s.focus;
            if(ImGui::IsKeyPressed(ImGuiKey_I))s.inspector=!s.inspector;
            if(ImGui::IsKeyPressed(ImGuiKey_L))s.labels=!s.labels;
            if(ImGui::IsKeyPressed(ImGuiKey_E))s.view.effects=!s.view.effects;
            if(ImGui::IsKeyPressed(ImGuiKey_Home)){s.tour=false;s.cameras[s.view.scene]={.20f,.15f,7.8f};}
            if(s.view.scene==0 && ImGui::IsKeyPressed(ImGuiKey_0)){s.tour=false;s.cameras[0].target={};}
            if(s.view.scene==0 && ImGui::IsKeyPressed(ImGuiKey_F)){s.tour=s.playing=s.follow=false;s.cameras[0].focus_token(tr,s.view.frame);}
        }
        s.view.time=float(now);s.view.arrival=(s.playing||s.follow)?float(std::max(0.,now-s.changed)):1.f;
        if(s.tour)guided_frame(s,film.empty()?now-s.tour_start:film_frame/24.);
        if(!s.focus)toolbar(s,fonts,float(W),now);run_dialog(s,now);
        count=int(tr.frames.size());int panel=s.inspector&&!s.focus?std::min(264,std::max(208,W/4)):0;
        float floor_h=s.focus?0.f:(s.thinking_text?146.f:103.f),top_h=s.focus?0.f:43.f;
        Viewport v{0,top_h,float(W-panel),float(H)-top_h-floor_h,float(fw)/W,float(fh)/H,float(H)};
        bool snap_ready=!snap.empty() && (!live || tr.finished);
        if(snap_ready && target>=0)s.seek(target,now);
        if(!s.focus)footer(s,fonts,float(W),float(H),floor_h,now);
        bool over_legend=cosmos_legend(s,v);
        if(panel)inspector(s,fonts,v.w,43,float(panel),v.h,now);
        Camera& camera=s.cameras[s.view.scene];
        if(!over_legend && !io.WantCaptureMouse && io.MousePos.x>=0 && io.MousePos.x<v.w && io.MousePos.y>v.y && io.MousePos.y<v.y+v.h){
            if(ImGui::IsMouseDragging(ImGuiMouseButton_Right)){camera.yaw-=io.MouseDelta.x*.007f;camera.pitch=std::clamp(camera.pitch+io.MouseDelta.y*.007f,-1.35f,1.35f);}
            if(io.MouseWheel!=0){s.tour=false;camera.zoom(io.MouseWheel,s.view.scene==0);}
        }
        if(snap_ready){s.view.time=2.4f;s.view.arrival=1.f;}
        if(!snap.empty() && live && !s.session.worker && !tr.finished)throw std::runtime_error(s.message.empty()?s.session.status:s.message);
        glViewport(0,0,fw,fh);glClearColor(.028f,.043f,.069f,1);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
        auto marks=renderer.draw(tr,v,camera,s.view,s.current_path());overlay(s,fonts,v,std::move(marks),now,over_legend);
        ImGui::Render();
        glViewport(0,0,fw,fh);ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if(snap_ready && ++draws>=2){glFinish();screenshot(snap,fw,fh);std::cerr<<"OpenGL "<<glGetString(GL_VERSION)<<" | "<<glGetString(GL_RENDERER)<<" | compute particles "<<renderer.compute()<<'\n';break;}
        if(!film.empty()){char file[32];std::snprintf(file,sizeof(file),"%04d.ppm",film_frame);screenshot(film/file,fw,fh);if(++film_frame==288)break;}
        glfwSwapBuffers(window);
        if(!snap.empty() && !snap_ready)Sleep(15);
    }
    return 0;
}
int WINAPI WinMain(HINSTANCE,HINSTANCE,LPSTR,int) {
    const auto args=arguments();
    try{return run(args);}
    catch(const std::exception& e){
        std::cerr<<"TokenScope: "<<e.what()<<'\n';
        if(std::find(args.begin(),args.end(),"--snapshot")==args.end() && std::find(args.begin(),args.end(),"--film")==args.end())MessageBoxW(nullptr,wide(e.what()).c_str(),L"TokenScope",MB_ICONERROR|MB_OK);
        return 1;
    }
}
