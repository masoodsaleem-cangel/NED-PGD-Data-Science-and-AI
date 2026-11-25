#include <glad/glad.h>
#include "renderer.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <numeric>

namespace {
constexpr float pi=3.14159265f;
struct V { float x=0,y=0,z=0; };
V operator+(V a,V b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
V operator-(V a,V b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
V operator*(V a,float s){return {a.x*s,a.y*s,a.z*s};}
float dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
V cross(V a,V b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
V norm(V a){return a*(1/std::max(.00001f,std::sqrt(dot(a,a))));}
V mix(V a,V b,float t){return a*(1-t)+b*t;}
V vec(Point a){return {a[0],a[1],a[2]};}
constexpr V cyan{.18f,.87f,.81f}, gold{1,.64f,.26f}, lilac{.64f,.55f,1}, pale{.76f,.89f,.96f};
struct MeshVertex{V pos,color;float alpha;};
struct Sprite{V pos,color;float radius,alpha;};
struct Cam {
    V right,up,back,target; float distance,aspect;
    Cam(const Camera& c,float aspect):target(vec(c.target)),distance(c.distance),aspect(aspect) {
        back={std::sin(c.yaw)*std::cos(c.pitch),std::sin(c.pitch),std::cos(c.yaw)*std::cos(c.pitch)};
        right=norm(cross({0,1,0},back)); up=cross(back,right);
    }
    bool screen(V p,const Viewport& v,float& x,float& y) const {
        p=p-target;
        float w=distance-dot(p,back); if(w<.05f) return false;
        x=v.x+(1+2.15f*dot(p,right)/(w*aspect))*v.w/2;
        y=v.y+(1-2.15f*dot(p,up)/w)*v.h/2;
        return true;
    }
    void uniforms(GLuint p) const {
        auto set=[&](const char* s,V v){glUniform3f(glGetUniformLocation(p,s),v.x,v.y,v.z);};
        set("rightV",right);set("upV",up);set("backV",back);set("targetV",target);
        glUniform2f(glGetUniformLocation(p,"lens"),distance,aspect);
    }
};
float cosmos_scale(const Trace& trace) {
    float radius=.18f;
    for(int i=0;i<std::min(trace.fit,int(trace.frames.size()));++i){
        V p=vec(trace.frames[i].xyz);
        radius=std::max(radius,std::sqrt(dot(p,p)));
    }
    return 3.18f/radius;
}
GLuint program(std::initializer_list<std::pair<GLenum,std::string>> stages) {
    GLuint prog=glCreateProgram(); std::vector<GLuint> shaders;
    try {
        for(const auto& st:stages) {
            GLuint sh=glCreateShader(st.first); shaders.push_back(sh);
            const char* s=st.second.c_str(); glShaderSource(sh,1,&s,nullptr);glCompileShader(sh);
            GLint ok=0;glGetShaderiv(sh,GL_COMPILE_STATUS,&ok);
            if(!ok){char msg[2048]{};glGetShaderInfoLog(sh,sizeof(msg),nullptr,msg);throw std::runtime_error(msg);}
            glAttachShader(prog,sh);
        }
        glLinkProgram(prog); GLint ok=0;glGetProgramiv(prog,GL_LINK_STATUS,&ok);
        if(!ok){char msg[2048]{};glGetProgramInfoLog(prog,sizeof(msg),nullptr,msg);throw std::runtime_error(msg);}
    } catch(...) { for(auto sh:shaders)glDeleteShader(sh);glDeleteProgram(prog);throw; }
    for(auto sh:shaders)glDeleteShader(sh);return prog;
}
const std::string camera_gl=R"GL(
uniform vec3 rightV,upV,backV,targetV;
uniform vec2 lens;
vec4 project(vec3 p){
 p-=targetV;
 float d=lens.x-dot(backV,p);
 return vec4(2.15*dot(rightV,p)/lens.y,2.15*dot(upV,p),1.001*d-.1,d);
}
)GL";
const char* background_vert=R"GL(#version 330 core
out vec2 uv;
void main(){ vec2 p=vec2((gl_VertexID==1)?3.:-1.,(gl_VertexID==2)?3.:-1.);uv=p*.5+.5;gl_Position=vec4(p,0,1);}
)GL";
const char* background_frag=R"GL(#version 330 core
in vec2 uv;out vec4 frag;uniform vec2 size;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
void main(){
 vec2 p=uv-.5; vec3 a=vec3(.023,.039,.066);
 float teal=exp(-3.4*length((p-vec2(-.30,.22))*vec2(1.1,.85)));
 float violet=exp(-4.*length(p-vec2(.37,-.25)));
 vec3 sky=a+teal*vec3(.012,.065,.072)+violet*vec3(.040,.012,.067);
 vec2 g=uv*size/4.; vec2 cell=floor(g);float star=step(.997,hash(cell));
 float speck=exp(-8.*length(fract(g)-.5));
 frag=vec4(sky+star*speck*vec3(.34,.44,.53),1.);
}
)GL";
const char* mesh_frag=R"GL(#version 330 core
in vec4 tint;out vec4 frag;void main(){frag=tint;}
)GL";
const char* sprite_frag=R"GL(#version 330 core
in vec2 uv;in vec4 tint;out vec4 frag;
void main(){float r=dot(uv,uv);if(r>1.)discard;
 float core=exp(-33.*r);float halo=.44*exp(-5.8*r)+.10*exp(-2.2*r);
 frag=vec4(mix(tint.rgb,vec3(1.),.68*core),tint.a*(core+halo));}
)GL";
}
struct Renderer::Data {
    GLuint bg=0,mesh=0,sprites=0,compute_shader=0,particles=0;
    GLuint empty=0,mvao=0,mbo=0,svao=0,sbo=0,ssbo=0;
    std::vector<MeshVertex> vertices, layer_lines; std::vector<Sprite> dots; std::vector<Mark> marks;
    V anchor{},spark_color=gold; bool spark=false;
    Data() {
        bg=program({{GL_VERTEX_SHADER,background_vert},{GL_FRAGMENT_SHADER,background_frag}});
        mesh=program({{GL_VERTEX_SHADER,std::string("#version 330 core\n")+camera_gl+R"GL(
layout(location=0)in vec3 p;layout(location=1)in vec3 c;layout(location=2)in float a;
out vec4 tint;void main(){gl_Position=project(p);tint=vec4(c,a);}
)GL"},{GL_FRAGMENT_SHADER,mesh_frag}});
        const std::string quad=R"GL(
uniform vec2 pixel;out vec2 uv;out vec4 tint;
const vec2 corners[6]=vec2[6](vec2(-1,-1),vec2(1,-1),vec2(1,1),vec2(-1,-1),vec2(1,1),vec2(-1,1));
void sprite(vec3 p,vec3 c,float radius,float opacity){
 vec4 clip=project(p);uv=corners[gl_VertexID];clip.xy+=uv*pixel*radius*clip.w;
 gl_Position=clip;tint=vec4(c,opacity);}
)GL";
        sprites=program({{GL_VERTEX_SHADER,std::string("#version 330 core\n")+camera_gl+quad+R"GL(
layout(location=0)in vec3 p;layout(location=1)in vec3 c;layout(location=2)in float radius;
layout(location=3)in float opacity;void main(){sprite(p,c,radius,opacity);}
)GL"},{GL_FRAGMENT_SHADER,sprite_frag}});
        glGenVertexArrays(1,&empty);glGenVertexArrays(1,&mvao);glGenBuffers(1,&mbo);
        glBindVertexArray(mvao);glBindBuffer(GL_ARRAY_BUFFER,mbo);
        for(int i=0;i<3;++i){glEnableVertexAttribArray(i);glVertexAttribPointer(i,i<2?3:1,GL_FLOAT,GL_FALSE,sizeof(MeshVertex),(void*)(size_t(i)*3*sizeof(float)));}
        glGenVertexArrays(1,&svao);glGenBuffers(1,&sbo);glBindVertexArray(svao);glBindBuffer(GL_ARRAY_BUFFER,sbo);
        for(int i=0;i<4;++i){glEnableVertexAttribArray(i);glVertexAttribPointer(i,i<2?3:1,GL_FLOAT,GL_FALSE,sizeof(Sprite),(void*)(size_t(i<3?i*3:7)*sizeof(float)));glVertexAttribDivisor(i,1);}
        if(GLAD_GL_VERSION_4_3) {
            compute_shader=program({{GL_COMPUTE_SHADER,R"GL(#version 430 core
layout(local_size_x=64)in;layout(std430,binding=0)writeonly buffer P{vec4 drift[];};
uniform float age;uniform uint seed;
float h(uint n){n^=n>>16;n*=2246822519u;n^=n>>13;n*=3266489917u;n^=n>>16;return float(n)/4294967296.;}
void main(){uint i=gl_GlobalInvocationID.x+seed*173u;
 float a=6.283185*h(i+1u), z=2.*h(i+7u)-1.,r=sqrt(max(0.,1.-z*z));
 vec3 dir=vec3(r*cos(a),z,r*sin(a));float t=clamp(age*1.25,0.,1.);
 vec3 offset=dir*(.06+(.14+1.05*h(i+15u))*t);offset.y-=.18*t*t;
 drift[gl_GlobalInvocationID.x]=vec4(offset,(1.-t)*(.25+.7*h(i+22u)));}
)GL"}});
            particles=program({{GL_VERTEX_SHADER,std::string("#version 430 core\n")+camera_gl+quad+R"GL(
layout(std430,binding=0)readonly buffer P{vec4 drift[];};
uniform vec3 center,hue;void main(){vec4 a=drift[gl_InstanceID];sprite(center+a.xyz,hue,3.6,a.w);}
)GL"},{GL_FRAGMENT_SHADER,sprite_frag}});
            glGenBuffers(1,&ssbo);glBindBuffer(GL_SHADER_STORAGE_BUFFER,ssbo);
            glBufferData(GL_SHADER_STORAGE_BUFFER,128*4*sizeof(float),nullptr,GL_DYNAMIC_DRAW);
        }
    }
    ~Data(){
        for(auto p:{bg,mesh,sprites,compute_shader,particles}) if(p)glDeleteProgram(p);
        for(auto b:{mbo,sbo,ssbo}) if(b)glDeleteBuffers(1,&b);
        for(auto a:{empty,mvao,svao}) if(a)glDeleteVertexArrays(1,&a);
    }
    void tri(V a,V b,V c,V color,float alpha){vertices.push_back({a,color,alpha});vertices.push_back({b,color,alpha});vertices.push_back({c,color,alpha});}
    void quad(V a,V b,V c,V e,V color,float alpha){tri(a,b,c,color,alpha);tri(a,c,e,color,alpha);}
    void line(V a,V b,float width,V col,float alpha,const Cam& cam){
        V side=norm(cross(b-a,cam.back))*width;
        quad(a-side,b-side,b+side,a+side,col,alpha);
    }
    void guide(V a,V b,V color,float alpha,const Cam& camera){
        line(a,b,.0045f*std::min(1.f,camera.distance/3.2f),color,alpha,camera);
    }
    void layer_segment(V from,V to,V color,float alpha){
        layer_lines.push_back({from,color,alpha});
        layer_lines.push_back({to,color,alpha});
    }
    void mark(V p,int index,std::string name,int priority,bool active,V color,const Cam& c,const Viewport& v,int layer=-1){
        float x,y;if(c.screen(p,v,x,y)) marks.push_back({x,y,index,std::move(name),priority,active,color.x,color.y,color.z,layer});
    }
    void grid(const Cam& c){
        V ink{.28f,.49f,.57f};
        for(int i=-6;i<=6;++i){
            float u=i*.58f;
            guide({u,-1.70f,-3.48f},{u,-1.70f,3.48f},ink,.24f,c);
            guide({-3.48f,-1.70f,u},{3.48f,-1.70f,u},ink,.24f,c);
        }
    }
    void answer_trail(const Trace& tr,const AnswerPath& path,float scale,const RenderOptions& o,
                      const Cam& c,const Viewport& area) {
        for (const auto& edge : path.edges) {
            if (!o.token_visible(tr.frames[edge.from]) || !o.token_visible(tr.frames[edge.to])) continue;
            V a = vec(tr.frames[edge.from].xyz)*scale;
            V b = vec(tr.frames[edge.to].xyz)*scale;
            bool newest = edge.to == o.frame;
            line(a,b,newest?.058f:.034f,gold,newest?.22f:.10f,c);
            line(a,b,newest?.019f:.010f,gold,newest?.99f:.67f,c);
            V delta = b-a;
            float length = std::sqrt(dot(delta,delta));
            if (length > .08f) {
                V direction = norm(delta);
                V tip = mix(a,b,.73f);
                float arrow = std::min(.13f,.17f*length);
                V base = tip-direction*arrow;
                V wing = norm(cross(direction,c.back))*(arrow*.4f);
                tri(tip,base+wing,base-wing,gold,newest?1.f:.76f);
            }
        }
        if (path.origin < 0 || path.links.empty() || !o.token_visible(tr.frames[path.origin])) return;
        const bool attention = path.branches == BranchView::attention;
        V hue = attention ? V{.27f,.70f,1.f} : V{.86f,.58f,1.f};
        V query = vec(tr.frames[path.origin].xyz)*scale;
        for (const auto& link : path.links) {
            if (!o.token_visible(tr.frames[link.position])) continue;
            V end = vec(tr.frames[link.position].xyz)*scale;
            float weight = attention ? float(link.score) : .45f;
            float width = .009f + .045f*weight;
            if (link.position == path.origin) {
                // A self-attention edge has the same start and end point.
                V prev = query+c.right*.15f;
                for (int k=1;k<=24;++k) {
                    float t=2*pi*k/24;
                    V p=query+c.right*(.15f*std::cos(t))+c.up*(.15f*std::sin(t));
                    line(prev,p,width,hue,.91f,c); prev=p;
                }
            } else {
                V mid=mix(query,end,.5f)+c.up*.19f;
                V prev=query;
                for (int k=1;k<=20;++k) {
                    float t=k/20.f;
                    V p=mix(mix(query,mid,t),mix(mid,end,t),t);
                    if (attention || k%2) line(prev,p,width,hue,.8f,c);
                    prev=p;
                }
            }
            dots.push_back({end,hue,16.f,.89f});
            char value[40];
            if (attention) std::snprintf(value,sizeof(value),"  %.1f%%",100*link.score);
            else std::snprintf(value,sizeof(value),"  cos %.2f",link.score);
            mark(end,link.position,label(tr.frames[link.position].text)+value,92,false,hue,c,area);
        }
    }
    void cosmos(const Trace& tr,const RenderOptions& o,const Cam& c,const Viewport& area,const AnswerPath* answer){
        const float scale=cosmos_scale(tr);
        const auto& focus=tr.frames[o.frame];V final=vec(focus.xyz)*scale;
        for(int axis=0;axis<3;++axis){
            V v=axis==0?V{1,0,0}:(axis==1?V{0,1,0}:V{0,0,1});
            guide(v*(-2.55f),v*2.55f,axis==1?lilac:cyan,.25f,c);
            mark(v*2.55f,-1,"PC "+std::to_string(axis+1),12,false,lilac,c,area);
        }
        if(c.distance<3.2f){
            dots.push_back({{},pale,4,.85f});
            mark({},-1,"0, 0, 0",13,false,pale,c,area);
        }
        for(int j=o.frame-1;o.token_visible(focus) && j>=0;--j) if(tr.frames[j].id==focus.id) {
            if(!o.token_visible(tr.frames[j]))break;
            V earlier=vec(tr.frames[j].xyz)*scale;
            for(int k=0;k<18;k+=2)line(mix(earlier,final,k/18.f),mix(earlier,final,(k+1)/18.f),.009f,gold,.65f,c);
            dots.push_back({earlier,gold,15,.60f});break;
        }
        if (answer) answer_trail(tr,*answer,scale,o,c,area);
        if(o.layer_path && o.token_visible(focus) && !focus.path.empty()){
            V prev=vec(focus.path.front().xyz)*scale;
            for(size_t j=0;j<focus.path.size();++j){
                const auto& lp=focus.path[j];V q=vec(lp.xyz)*scale;
                float depth=float(lp.layer)/std::max(1,tr.layers-1);
                V col=mix(V{.48f,.35f,.82f},V{.86f,.68f,1.f},depth);
                if(j && lp.layer==focus.path[j-1].layer+1)layer_segment(prev,q,col,.86f);
                dots.push_back({q,col,3.f,.80f});
                mark(q,-1,{},0,false,col,c,area,lp.layer);
                prev=q;
            }
            if(focus.path.back().layer==tr.layers-1)layer_segment(prev,final,lilac,.60f);
        }
        for(int i=0;i<=o.frame;++i){
            const auto& f=tr.frames[i];bool active=i==o.frame;
            if(!o.token_visible(f))continue;
            V p=vec(f.xyz)*scale,col=f.phase=="prompt"?cyan:gold;
            if(active && !answer && o.effects && o.arrival<.56f) {
                float u=std::pow(1-o.arrival/.56f,3.f);
                V start=final+V{1.35f,.85f,-1.f};
                p=mix(final,start,u);
                line(final,p,.008f,col,.55f,c);
                dots.push_back({final,col,5,.7f});
            }
            dots.push_back({p,col,active?39.f:18.f,active?1.55f:1.15f});
            if(active){anchor=p;spark_color=col;spark=true;}
            int pri=active?100:(f.id==focus.id?70:(f.phase=="generated"?28:20));
            auto name=label(f.text);
            if(answer && f.phase=="generated") name=std::to_string(i-tr.prompt_tokens+1)+"  "+name;
            mark(p,i,std::move(name),pri,active,col,c,area);
        }
    }
    void loom(const Trace& tr,const RenderOptions& o,const Cam& c,const Viewport& area){
        const Frame& f=tr.frames[o.frame];
        const auto& all=f.weights(o.layer,tr.layer);
        if(all.empty() || o.head<0 || o.head>=int(all.size())) return;
        const auto& w=all[o.head];
        std::vector<int> ranks(w.size());std::iota(ranks.begin(),ranks.end(),0);
        std::stable_sort(ranks.begin(),ranks.end(),[&](int a,int b){return w[a]>w[b];});
        V q={0,1.62f,0};dots.push_back({q,gold,37,1.55f});mark(q,-1,"Query  "+label(f.text),100,true,gold,c,area);
        std::vector<V> keys(w.size());
        for(size_t i=0;i<w.size();++i){
            float a=-pi*.91f+1.82f*pi*(w.size()>1?float(i)/(w.size()-1):.5f);
            keys[i]={3.35f*std::sin(a),-1.16f,1.33f*std::cos(a)};
            dots.push_back({keys[i],cyan,9+17*std::sqrt(w[i]),.94f});
            if(i)line(keys[i-1],keys[i],.004f,cyan,.27f,c);
            mark(keys[i],int(i),label(tr.frames[i].text),8,false,cyan,c,area);
        }
        for(size_t k=0;k<std::min<size_t>(12,ranks.size());++k){
            int i=ranks[k];float weight=w[i];if(weight<.00005f) continue;
            V end=keys[i],control={end.x*.78f,1.73f,end.z+.4f};
            V col=mix(cyan,lilac,float(k)/12);
            auto at=[&](float t){return q*((1-t)*(1-t))+control*(2*t*(1-t))+end*(t*t);};
            V previous=q;for(int j=1;j<=32;++j){
                V p=at(j/32.f);
                line(previous,p,.020f+.165f*weight,col,.14f+.16f*std::sqrt(weight),c);
                line(previous,p,.006f+.105f*weight,col,.44f+.55f*std::sqrt(weight),c);previous=p;
            }
            if(o.effects)dots.push_back({at(std::fmod(o.time*.35f+k*.17f,1.f)),col,4+6*std::sqrt(weight),.85f});
            char pct[24];std::snprintf(pct,sizeof(pct),"  %.1f%%",weight*100);
            mark(end,i,label(tr.frames[i].text)+pct,85-int(k),false,col,c,area);
        }
    }
    void race(const Trace& tr,const RenderOptions& o,const Cam& c,const Viewport& area){
        const auto& f=tr.frames[o.frame];auto race=f.top;
        if(f.has_next && std::none_of(race.begin(),race.end(),[&](auto& v){return v.id==f.next.id;})) race.push_back(f.next);
        const float floor=-1.38f;
        double leader=o.draw_probs?f.top.front().draw:f.top.front().p;
        for(int step=0;step<=4;++step){
            float y=floor+2.45f*step/4.f;
            line({-3.16f,y,-.55f},{2.8f,y,-.55f},.005f,cyan,.22f,c);
            char text[24];std::snprintf(text,sizeof(text),"%.1f%%",leader*100*step/4);
            mark({-3.36f,y,-.55f},-1,text,14,false,cyan,c,area);
        }
        for(size_t j=0;j<race.size();++j){
            const auto& v=race[j];double value=o.draw_probs?v.draw:v.p;
            float x=(float(j)-(race.size()-1)*.5f)*1.01f;
            float h=leader>0?float(2.45*value/leader):0;
            bool picked=f.has_next && v.id==f.next.id;
            V col=picked?gold:mix(cyan,lilac,float(j)/float(race.size()));
            constexpr float a=.27f,b=.30f;float t=floor+h;
            if(h>.0001f){
                quad({x-a,floor,b},{x+a,floor,b},{x+a,t,b},{x-a,t,b},col*.71f,.93f);
                quad({x+a,floor,b},{x+a,floor,-b},{x+a,t,-b},{x+a,t,b},col*.43f,.94f);
                quad({x-a,floor,-b},{x-a,floor,b},{x-a,t,b},{x-a,t,-b},col*.55f,.95f);
                quad({x-a,floor,-b},{x+a,floor,-b},{x+a,t,-b},{x-a,t,-b},col*.54f,.94f);
            }
            quad({x-a,t,-b},{x+a,t,-b},{x+a,t,b},{x-a,t,b},col,1);
            line({x-a,t,b},{x+a,t,b},.013f,pale,.8f,c);
            line({x-a,floor,b},{x-a,t,b},.009f,col,.9f,c);
            line({x+a,floor,b},{x+a,t,b},.006f,col,.77f,c);
            if(h>.05f){
                float y=floor+h*(o.effects?std::fmod(o.time*.35f+.13f*j,1.f):.98f);
                line({x-a,y,b+.006f},{x+a,y,b+.006f},.012f,col,.62f,c);
            }
            char pct[24];std::snprintf(pct,sizeof(pct),"  %.1f%%",100*value);
            mark({x,t+.09f,0},-1,label(v.text)+pct,picked?100:80-int(j),picked,col,c,area);
            if(picked){anchor={x,t+.03f,0};spark_color=gold;spark=true;dots.push_back({anchor,gold,17,1});}
        }
    }
};
Renderer::Renderer():d(std::make_unique<Data>()){}
void Camera::focus_token(const Trace& trace,int index) {
    if(index<0 || index>=int(trace.frames.size()))return;
    const V p=vec(trace.frames[index].xyz)*cosmos_scale(trace);
    target={p.x,p.y,p.z};
    distance=std::min(distance,2.5f);
}
void Camera::zoom(float wheel,bool cosmos) {
    distance=std::clamp(distance*std::exp(-wheel*(cosmos?.15f:.095f)),cosmos?.12f:3.2f,18.f);
}
Renderer::~Renderer()=default;
bool Renderer::compute() const{return d->compute_shader!=0;}
std::vector<Mark> Renderer::draw(const Trace& tr,const Viewport& v,const Camera& camera,const RenderOptions& o,const AnswerPath* answer) {
    int W=std::max(1,int(v.w*v.sx)),H=std::max(1,int(v.h*v.sy));
    glViewport(int(v.x*v.sx),int((v.screen_h-v.y-v.h)*v.sy),W,H);
    glDisable(GL_SCISSOR_TEST);glDisable(GL_CULL_FACE);glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);
    glUseProgram(d->bg);glUniform2f(glGetUniformLocation(d->bg,"size"),v.w,v.h);glBindVertexArray(d->empty);glDrawArrays(GL_TRIANGLES,0,3);
    d->vertices.clear();d->layer_lines.clear();d->dots.clear();d->marks.clear();d->spark=false;
    Cam cam(camera,v.w/std::max(1.f,v.h));d->grid(cam);
    if(o.frame>=0 && o.frame<int(tr.frames.size())) {
        if(o.scene==0)d->cosmos(tr,o,cam,v,answer);else if(o.scene==1)d->loom(tr,o,cam,v);else d->race(tr,o,cam,v);
    }
    glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);glEnable(GL_DEPTH_TEST);glDepthFunc(GL_LEQUAL);
    glUseProgram(d->mesh);cam.uniforms(d->mesh);
    glBindVertexArray(d->mvao);glBindBuffer(GL_ARRAY_BUFFER,d->mbo);
    glBufferData(GL_ARRAY_BUFFER,d->vertices.size()*sizeof(MeshVertex),d->vertices.data(),GL_STREAM_DRAW);
    glDrawArrays(GL_TRIANGLES,0,GLsizei(d->vertices.size()));
    if(!d->layer_lines.empty()){
        glBufferData(GL_ARRAY_BUFFER,d->layer_lines.size()*sizeof(MeshVertex),d->layer_lines.data(),GL_STREAM_DRAW);
        glLineWidth(1.f);
        glDrawArrays(GL_LINES,0,GLsizei(d->layer_lines.size()));
    }
    glDisable(GL_DEPTH_TEST);glBlendFunc(GL_SRC_ALPHA,GL_ONE);
    auto pixels=[&](GLuint pg){glUniform2f(glGetUniformLocation(pg,"pixel"),2.f/v.w,2.f/v.h);};
    glUseProgram(d->sprites);cam.uniforms(d->sprites);pixels(d->sprites);
    glBindVertexArray(d->svao);glBindBuffer(GL_ARRAY_BUFFER,d->sbo);
    glBufferData(GL_ARRAY_BUFFER,d->dots.size()*sizeof(Sprite),d->dots.data(),GL_STREAM_DRAW);
    glDrawArraysInstanced(GL_TRIANGLES,0,6,GLsizei(d->dots.size()));
    if(d->compute_shader && o.effects && d->spark && o.arrival<.8f){
        glUseProgram(d->compute_shader);glBindBufferBase(GL_SHADER_STORAGE_BUFFER,0,d->ssbo);
        glUniform1f(glGetUniformLocation(d->compute_shader,"age"),o.arrival);glUniform1ui(glGetUniformLocation(d->compute_shader,"seed"),o.frame+1);
        glDispatchCompute(2,1,1);glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT);
        glUseProgram(d->particles);cam.uniforms(d->particles);pixels(d->particles);
        glUniform3f(glGetUniformLocation(d->particles,"center"),d->anchor.x,d->anchor.y,d->anchor.z);
        glUniform3f(glGetUniformLocation(d->particles,"hue"),d->spark_color.x,d->spark_color.y,d->spark_color.z);
        glBindVertexArray(d->empty);glDrawArraysInstanced(GL_TRIANGLES,0,6,128);
    }
    glBindVertexArray(0);glUseProgram(0);glDisable(GL_BLEND);return d->marks;
}
