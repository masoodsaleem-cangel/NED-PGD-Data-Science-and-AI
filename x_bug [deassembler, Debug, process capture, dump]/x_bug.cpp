#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cstdint>
#include <memory>
#include <cstring>

// ============================================================================
// ANSI Color & Terminal Utilities
// ============================================================================
namespace Term {
    inline const char* RESET       = "\x1b[0m";
    inline const char* BOLD        = "\x1b[1m";
    inline const char* DIM         = "\x1b[2m";
    inline const char* UNDERLINE   = "\x1b[4m";
    inline const char* REVERSE     = "\x1b[7m";

    // Palette Colors (Dark Theme)
    inline const char* FG_BG_BAR   = "\x1b[38;2;248;248;242m\x1b[48;2;40;42;54m";
    inline const char* FG_BAR_TXT  = "\x1b[38;2;255;121;198m\x1b[1m";
    inline const char* FG_ADDR     = "\x1b[38;2;139;233;253m";       // Cyan
    inline const char* FG_ZERO     = "\x1b[38;2;98;114;164m";        // Dim purple-gray
    inline const char* FG_ASCII    = "\x1b[38;2;80;250;123m";        // Bright Green
    inline const char* FG_HIGH     = "\x1b[38;2;255;184;108m";       // Orange
    inline const char* FG_SPECIAL  = "\x1b[38;2;255;121;198m";       // Pink / Magenta
    inline const char* FG_MNEMONIC = "\x1b[38;2;241;250;140m\x1b[1m";// Bright Yellow
    inline const char* FG_OPERAND  = "\x1b[38;2;248;248;242m";       // White
    inline const char* FG_REG      = "\x1b[38;2;139;233;253m";       // Cyan
    inline const char* FG_BRANCH   = "\x1b[38;2;255;85;85m\x1b[1m";  // Bright Red / Branch
    inline const char* FG_CALL     = "\x1b[38;2;189;147;249m\x1b[1m";// Purple
    inline const char* FG_COMMENT  = "\x1b[38;2;98;114;164m";        // Dim comment
    inline const char* FG_MUTED    = "\x1b[38;2;120;120;140m";
    inline const char* FG_BORDER   = "\x1b[38;2;68;71;90m";
    inline const char* BG_CURSOR   = "\x1b[48;2;68;71;90m\x1b[38;2;255;255;255m\x1b[1m";
    inline const char* BG_SELECT   = "\x1b[48;2;98;114;164m\x1b[38;2;255;255;255m\x1b[1m";
    inline const char* BG_STATUS   = "\x1b[48;2;33;34;44m\x1b[38;2;248;248;242m";

    struct ConsoleState {
        HANDLE hIn = INVALID_HANDLE_VALUE;
        HANDLE hOut = INVALID_HANDLE_VALUE;
        DWORD origInMode = 0;
        DWORD origOutMode = 0;
        bool initialized = false;
    } g_con;

    inline void init() {
        g_con.hIn = GetStdHandle(STD_INPUT_HANDLE);
        g_con.hOut = GetStdHandle(STD_OUTPUT_HANDLE);
        GetConsoleMode(g_con.hIn, &g_con.origInMode);
        GetConsoleMode(g_con.hOut, &g_con.origOutMode);

        DWORD outMode = g_con.origOutMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT;
        SetConsoleMode(g_con.hOut, outMode);

        DWORD inMode = ENABLE_WINDOW_INPUT | ENABLE_EXTENDED_FLAGS;
        SetConsoleMode(g_con.hIn, inMode);

        // Hide console cursor initially
        std::cout << "\x1b[?25l";
        std::cout.flush();
        g_con.initialized = true;
    }

    inline void restore() {
        if (!g_con.initialized) return;
        std::cout << "\x1b[?25h" << RESET << "\x1b[2J\x1b[H";
        std::cout.flush();
        SetConsoleMode(g_con.hIn, g_con.origInMode);
        SetConsoleMode(g_con.hOut, g_con.origOutMode);
    }

    inline void get_size(int& width, int& height) {
        CONSOLE_SCREEN_BUFFER_INFO csbi;
        if (GetConsoleScreenBufferInfo(g_con.hOut, &csbi)) {
            width = csbi.srWindow.Right - csbi.srWindow.Left + 1;
            height = csbi.srWindow.Bottom - csbi.srWindow.Top + 1;
        } else {
            width = 100;
            height = 30;
        }
    }

    inline void clear_screen() {
        std::cout << "\x1b[2J\x1b[H";
    }

    inline void move_cursor(int row, int col) {
        std::cout << "\x1b[" << row << ";" << col << "H";
    }
}

// ============================================================================
// Keyboard Input Constants
// ============================================================================
enum class KeyCode {
    None,
    Up, Down, Left, Right,
    PageUp, PageDown,
    Home, End,
    Enter, Escape, Backspace, Tab,
    F1, F2, F7, F8, F9,
    Char
};

struct KeyEvent {
    KeyCode code = KeyCode::None;
    char ch = 0;
    bool ctrl = false;
    bool shift = false;
};

KeyEvent read_key() {
    KeyEvent evt;
    HANDLE hIn = Term::g_con.hIn;
    INPUT_RECORD ir;
    DWORD read = 0;

    while (true) {
        if (!ReadConsoleInputW(hIn, &ir, 1, &read) || read == 0) {
            return evt;
        }
        if (ir.EventType == KEY_EVENT && ir.Event.KeyEvent.bKeyDown) {
            WORD vk = ir.Event.KeyEvent.wVirtualKeyCode;
            WCHAR uchar = ir.Event.KeyEvent.uChar.UnicodeChar;
            DWORD ctrlState = ir.Event.KeyEvent.dwControlKeyState;

            evt.ctrl = (ctrlState & (LEFT_CTRL_PRESSED | RIGHT_CTRL_PRESSED)) != 0;
            evt.shift = (ctrlState & SHIFT_PRESSED) != 0;

            switch (vk) {
                case VK_UP:     evt.code = KeyCode::Up; return evt;
                case VK_DOWN:   evt.code = KeyCode::Down; return evt;
                case VK_LEFT:   evt.code = KeyCode::Left; return evt;
                case VK_RIGHT:  evt.code = KeyCode::Right; return evt;
                case VK_PRIOR:  evt.code = KeyCode::PageUp; return evt;
                case VK_NEXT:   evt.code = KeyCode::PageDown; return evt;
                case VK_HOME:   evt.code = KeyCode::Home; return evt;
                case VK_END:    evt.code = KeyCode::End; return evt;
                case VK_RETURN: evt.code = KeyCode::Enter; return evt;
                case VK_ESCAPE: evt.code = KeyCode::Escape; return evt;
                case VK_BACK:   evt.code = KeyCode::Backspace; return evt;
                case VK_TAB:    evt.code = KeyCode::Tab; return evt;
                case VK_F1:     evt.code = KeyCode::F1; return evt;
                case VK_F2:     evt.code = KeyCode::F2; return evt;
                case VK_F7:     evt.code = KeyCode::F7; return evt;
                case VK_F8:     evt.code = KeyCode::F8; return evt;
                case VK_F9:     evt.code = KeyCode::F9; return evt;
                default:
                    if (uchar >= 32 && uchar <= 126) {
                        evt.code = KeyCode::Char;
                        evt.ch = static_cast<char>(uchar);
                        return evt;
                    }
                    break;
            }
        }
    }
}

// ============================================================================
// Executable Format Models & Section Parsers (PE / ELF)
// ============================================================================
enum class FileFormatType {
    UnknownBinary,
    PE32,
    PE64,
    ELF32,
    ELF64
};

struct SectionInfo {
    std::string name;
    uint64_t virtualAddress = 0;
    uint64_t virtualSize = 0;
    uint64_t rawOffset = 0;
    uint64_t rawSize = 0;
    bool isCode = false;
    bool isReadable = false;
    bool isWritable = false;
    bool isExecutable = false;
};

struct BinaryMetadata {
    FileFormatType format = FileFormatType::UnknownBinary;
    std::string formatName = "Raw Binary";
    std::string arch = "Unknown";
    uint64_t imageBase = 0;
    uint64_t entryPointRVA = 0;
    uint64_t entryPointRaw = 0;
    std::vector<SectionInfo> sections;

    const SectionInfo* find_section(uint64_t rawOffset) const {
        for (const auto& sec : sections) {
            if (rawOffset >= sec.rawOffset && rawOffset < sec.rawOffset + sec.rawSize) {
                return &sec;
            }
        }
        return nullptr;
    }

    uint64_t raw_to_rva(uint64_t rawOffset) const {
        const auto* sec = find_section(rawOffset);
        if (sec) {
            return sec->virtualAddress + (rawOffset - sec->rawOffset);
        }
        return rawOffset;
    }

    uint64_t rva_to_raw(uint64_t rva) const {
        for (const auto& sec : sections) {
            if (rva >= sec.virtualAddress && rva < sec.virtualAddress + sec.virtualSize) {
                return sec.rawOffset + (rva - sec.virtualAddress);
            }
        }
        return 0;
    }
};

class BinaryFile {
public:
    std::string filePath;
    std::vector<uint8_t> data;
    BinaryMetadata meta;

    bool load(const std::string& path) {
        filePath = path;
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file.is_open()) return false;

        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);

        data.resize(static_cast<size_t>(size));
        if (size > 0) {
            file.read(reinterpret_cast<char*>(data.data()), size);
        }
        parse_executable_headers();
        return true;
    }

    size_t size() const { return data.size(); }
    uint8_t get(size_t offset) const {
        return (offset < data.size()) ? data[offset] : 0;
    }

private:
    void parse_executable_headers() {
        if (data.size() < 64) return;

        // Check PE Format (MZ header)
        if (data[0] == 'M' && data[1] == 'Z') {
            parse_pe();
            return;
        }

        // Check ELF Format (\x7fELF)
        if (data[0] == 0x7F && data[1] == 'E' && data[2] == 'L' && data[3] == 'F') {
            parse_elf();
            return;
        }
    }

    void parse_pe() {
        if (data.size() < 0x3C + 4) return;
        uint32_t peOffset = *reinterpret_cast<const uint32_t*>(&data[0x3C]);
        if (peOffset + 24 > data.size()) return;

        if (data[peOffset] != 'P' || data[peOffset + 1] != 'E' ||
            data[peOffset + 2] != 0 || data[peOffset + 3] != 0) {
            return;
        }

        uint16_t machine = *reinterpret_cast<const uint16_t*>(&data[peOffset + 4]);
        uint16_t numSections = *reinterpret_cast<const uint16_t*>(&data[peOffset + 6]);
        uint16_t sizeOfOptHeader = *reinterpret_cast<const uint16_t*>(&data[peOffset + 20]);

        size_t optHeaderOffset = peOffset + 24;
        if (optHeaderOffset + sizeOfOptHeader > data.size()) return;

        uint16_t magic = *reinterpret_cast<const uint16_t*>(&data[optHeaderOffset]);
        if (magic == 0x20B) { // PE32+ (64-bit)
            meta.format = FileFormatType::PE64;
            meta.formatName = "PE32+ Executable (64-bit)";
            meta.arch = (machine == 0x8664) ? "x86_64 / AMD64" : "ARM64";
            meta.entryPointRVA = *reinterpret_cast<const uint32_t*>(&data[optHeaderOffset + 16]);
            meta.imageBase = *reinterpret_cast<const uint64_t*>(&data[optHeaderOffset + 24]);
        } else if (magic == 0x10B) { // PE32 (32-bit)
            meta.format = FileFormatType::PE32;
            meta.formatName = "PE32 Executable (32-bit)";
            meta.arch = (machine == 0x14C) ? "x86 / i386" : "ARM";
            meta.entryPointRVA = *reinterpret_cast<const uint32_t*>(&data[optHeaderOffset + 16]);
            meta.imageBase = *reinterpret_cast<const uint32_t*>(&data[optHeaderOffset + 28]);
        } else {
            return;
        }

        size_t sectionHeaderOffset = optHeaderOffset + sizeOfOptHeader;
        for (int i = 0; i < numSections; ++i) {
            size_t secOff = sectionHeaderOffset + i * 40;
            if (secOff + 40 > data.size()) break;

            SectionInfo sec;
            char nameBuf[9] = {0};
            std::memcpy(nameBuf, &data[secOff], 8);
            sec.name = nameBuf;

            sec.virtualSize = *reinterpret_cast<const uint32_t*>(&data[secOff + 8]);
            sec.virtualAddress = *reinterpret_cast<const uint32_t*>(&data[secOff + 12]);
            sec.rawSize = *reinterpret_cast<const uint32_t*>(&data[secOff + 16]);
            sec.rawOffset = *reinterpret_cast<const uint32_t*>(&data[secOff + 20]);
            uint32_t characteristics = *reinterpret_cast<const uint32_t*>(&data[secOff + 36]);

            sec.isCode = (characteristics & 0x00000020) != 0;
            sec.isExecutable = (characteristics & 0x20000000) != 0;
            sec.isReadable = (characteristics & 0x40000000) != 0;
            sec.isWritable = (characteristics & 0x80000000) != 0;

            meta.sections.push_back(sec);
        }

        meta.entryPointRaw = meta.rva_to_raw(meta.entryPointRVA);
    }

    void parse_elf() {
        if (data.size() < 52) return;
        uint8_t elfClass = data[4];
        if (elfClass == 2) {
            meta.format = FileFormatType::ELF64;
            meta.formatName = "ELF Executable (64-bit)";
            uint16_t machine = *reinterpret_cast<const uint16_t*>(&data[18]);
            meta.arch = (machine == 0x3E) ? "x86_64" : (machine == 0xB7 ? "AArch64" : "Other");
            meta.entryPointRVA = *reinterpret_cast<const uint64_t*>(&data[24]);
            meta.entryPointRaw = meta.entryPointRVA;
        } else {
            meta.format = FileFormatType::ELF32;
            meta.formatName = "ELF Executable (32-bit)";
            uint16_t machine = *reinterpret_cast<const uint16_t*>(&data[18]);
            meta.arch = (machine == 0x03) ? "x86" : (machine == 0x28 ? "ARM" : "Other");
            meta.entryPointRVA = *reinterpret_cast<const uint32_t*>(&data[24]);
            meta.entryPointRaw = meta.entryPointRVA;
        }
    }
};

// ============================================================================
// Standalone x86/x64 Instruction Decoder & Disassembler
// ============================================================================
struct DecodedInst {
    uint64_t address = 0;
    size_t length = 1;
    std::vector<uint8_t> bytes;
    std::string mnemonic = "db";
    std::string operands = "";
    std::string comment = "";
    bool isBranch = false;
    bool isCall = false;
    bool isRet = false;
    uint64_t targetAddress = 0;
};

class X86Disasm {
public:
    static DecodedInst decode(const uint8_t* code, size_t maxLen, uint64_t rip, bool is64Bit = true) {
        DecodedInst inst;
        inst.address = rip;
        if (maxLen == 0) return inst;

        size_t cursor = 0;
        uint8_t rex = 0;
        bool hasRex = false;
        bool opSizeOverride = false;
        bool addrSizeOverride = false;
        std::string prefixStr = "";

        // Parse Legacy Prefixes & REX
        while (cursor < maxLen) {
            uint8_t b = code[cursor];
            if (b == 0xF0) { prefixStr += "lock "; cursor++; }
            else if (b == 0xF2) { prefixStr += "repne "; cursor++; }
            else if (b == 0xF3) { prefixStr += "rep "; cursor++; }
            else if (b == 0x2E || b == 0x36 || b == 0x3E || b == 0x26 || b == 0x64 || b == 0x65) {
                cursor++; // Segment override
            }
            else if (b == 0x66) { opSizeOverride = true; cursor++; }
            else if (b == 0x67) { addrSizeOverride = true; cursor++; }
            else if (is64Bit && (b >= 0x40 && b <= 0x4F)) {
                rex = b;
                hasRex = true;
                cursor++;
                break; // REX must immediately precede opcode
            }
            else {
                break;
            }
        }

        if (cursor >= maxLen) {
            inst.length = 1;
            inst.bytes.push_back(code[0]);
            inst.operands = hex_byte(code[0]);
            return inst;
        }

        uint8_t op = code[cursor++];
        bool rexW = (rex & 0x08) != 0;
        bool rexR = (rex & 0x04) != 0;
        bool rexX = (rex & 0x02) != 0;
        bool rexB = (rex & 0x01) != 0;

        // Register tables
        static const char* r64[] = {"rax","rcx","rdx","rbx","rsp","rbp","rsi","rdi","r8","r9","r10","r11","r12","r13","r14","r15"};
        static const char* r32[] = {"eax","ecx","edx","ebx","esp","ebp","esi","edi","r8d","r9d","r10d","r11d","r12d","r13d","r14d","r15d"};
        static const char* r16[] = {"ax","cx","dx","bx","sp","bp","si","di","r8w","r9w","r10w","r11w","r12w","r13w","r14w","r15w"};
        static const char* r8b[] = {"al","cl","dl","bl","spl","bpl","sil","dil","r8b","r9b","r10b","r11b","r12b","r13b","r14b","r15b"};
        static const char* r8legacy[] = {"al","cl","dl","bl","ah","ch","dh","bh"};

        auto get_reg_name = [&](int idx, int byteSize) -> std::string {
            idx &= 0x0F;
            if (byteSize == 8) return r64[idx];
            if (byteSize == 4) return r32[idx];
            if (byteSize == 2) return r16[idx];
            if (hasRex) return r8b[idx];
            return (idx < 8) ? r8legacy[idx] : r8b[idx];
        };

        int defOpSize = (is64Bit && rexW) ? 8 : (opSizeOverride ? 2 : 4);

        // Helper to decode ModR/M and SIB
        auto decode_modrm_mem = [&](uint8_t modrm, int memSize) -> std::pair<std::string, std::string> {
            uint8_t mod = (modrm >> 6) & 0x03;
            uint8_t regIdx = ((modrm >> 3) & 0x07) | (rexR ? 8 : 0);
            uint8_t rmIdx = (modrm & 0x07) | (rexB ? 8 : 0);

            std::string regStr = get_reg_name(regIdx, memSize);
            if (mod == 3) {
                return {regStr, get_reg_name(rmIdx, memSize)};
            }

            // Memory reference
            std::string sizeTag = "";
            if (memSize == 8) sizeTag = "qword ptr ";
            else if (memSize == 4) sizeTag = "dword ptr ";
            else if (memSize == 2) sizeTag = "word ptr ";
            else if (memSize == 1) sizeTag = "byte ptr ";

            std::string memStr = "";
            if (is64Bit && mod == 0 && (modrm & 0x07) == 5) {
                // RIP-relative [rip + disp32]
                if (cursor + 4 <= maxLen) {
                    int32_t disp = *reinterpret_cast<const int32_t*>(&code[cursor]);
                    cursor += 4;
                    uint64_t target = rip + cursor + disp;
                    std::ostringstream ss;
                    ss << sizeTag << "[rip " << (disp >= 0 ? "+ " : "- ")
                       << "0x" << std::hex << std::abs(disp) << "]";
                    inst.comment = "target: 0x" + to_hex(target);
                    return {regStr, ss.str()};
                }
            }

            std::string baseReg = "";
            std::string indexReg = "";
            int scale = 1;

            if ((modrm & 0x07) == 4) { // SIB Byte follows
                if (cursor < maxLen) {
                    uint8_t sib = code[cursor++];
                    uint8_t sibScale = (sib >> 6) & 0x03;
                    uint8_t sibIndex = ((sib >> 3) & 0x07) | (rexX ? 8 : 0);
                    uint8_t sibBase = (sib & 0x07) | (rexB ? 8 : 0);

                    scale = 1 << sibScale;
                    if (sibIndex != 4 || rexX) {
                        indexReg = get_reg_name(sibIndex, 8);
                    }
                    if (mod == 0 && (sib & 0x07) == 5) {
                        // Base is none, disp32 follows
                    } else {
                        baseReg = get_reg_name(sibBase, 8);
                    }
                }
            } else {
                baseReg = get_reg_name(rmIdx, 8);
            }

            int32_t disp = 0;
            bool hasDisp = false;
            if (mod == 1 && cursor < maxLen) {
                disp = static_cast<int8_t>(code[cursor++]);
                hasDisp = true;
            } else if ((mod == 2 || (mod == 0 && (modrm & 0x07) == 4 && baseReg.empty())) && cursor + 4 <= maxLen) {
                disp = *reinterpret_cast<const int32_t*>(&code[cursor]);
                cursor += 4;
                hasDisp = true;
            }

            std::ostringstream ss;
            ss << sizeTag << "[";
            bool first = true;
            if (!baseReg.empty()) { ss << baseReg; first = false; }
            if (!indexReg.empty()) {
                if (!first) ss << " + ";
                ss << indexReg;
                if (scale > 1) ss << "*" << scale;
                first = false;
            }
            if (hasDisp && disp != 0) {
                if (!first) {
                    ss << (disp >= 0 ? " + 0x" : " - 0x") << std::hex << std::abs(disp);
                } else {
                    ss << "0x" << std::hex << disp;
                }
            } else if (first) {
                ss << "0x0";
            }
            ss << "]";
            return {regStr, ss.str()};
        };

        // Two-byte opcode (0x0F)
        if (op == 0x0F && cursor < maxLen) {
            uint8_t op2 = code[cursor++];
            if (op2 == 0x05) { inst.mnemonic = "syscall"; }
            else if (op2 == 0x31) { inst.mnemonic = "rdtsc"; }
            else if (op2 == 0x1F) {
                inst.mnemonic = "nop";
                if (cursor < maxLen) {
                    uint8_t m = code[cursor++];
                    decode_modrm_mem(m, 4);
                }
            }
            else if (op2 >= 0x80 && op2 <= 0x8F) { // Jcc near rel32
                static const char* jccs[] = {"jo","jno","jb","jae","je","jne","jbe","ja","js","jns","jp","jnp","jl","jge","jle","jg"};
                inst.mnemonic = jccs[op2 - 0x80];
                inst.isBranch = true;
                if (cursor + 4 <= maxLen) {
                    int32_t rel = *reinterpret_cast<const int32_t*>(&code[cursor]);
                    cursor += 4;
                    inst.targetAddress = rip + cursor + rel;
                    inst.operands = "0x" + to_hex(inst.targetAddress);
                }
            }
            else if (op2 == 0xAF) { // IMUL r, r/m
                inst.mnemonic = "imul";
                if (cursor < maxLen) {
                    auto p = decode_modrm_mem(code[cursor++], defOpSize);
                    inst.operands = p.first + ", " + p.second;
                }
            }
            else if (op2 == 0xB6 || op2 == 0xB7) { // MOVZX
                inst.mnemonic = "movzx";
                if (cursor < maxLen) {
                    auto p = decode_modrm_mem(code[cursor++], (op2 == 0xB6 ? 1 : 2));
                    inst.operands = get_reg_name((code[cursor - 1] >> 3) & 7, defOpSize) + ", " + p.second;
                }
            }
            else if (op2 == 0xBE || op2 == 0xBF) { // MOVSX
                inst.mnemonic = "movsx";
                if (cursor < maxLen) {
                    auto p = decode_modrm_mem(code[cursor++], (op2 == 0xBE ? 1 : 2));
                    inst.operands = get_reg_name((code[cursor - 1] >> 3) & 7, defOpSize) + ", " + p.second;
                }
            }
            else if (op2 >= 0x90 && op2 <= 0x9F) { // SETcc rm8
                static const char* setccs[] = {"seto","setno","setb","setae","sete","setne","setbe","seta","sets","setns","setp","setnp","setl","setge","setle","setg"};
                inst.mnemonic = setccs[op2 - 0x90];
                if (cursor < maxLen) {
                    auto p = decode_modrm_mem(code[cursor++], 1);
                    inst.operands = p.second;
                }
            }
            else if (op2 == 0x28 || op2 == 0x29) { // MOVAPS
                inst.mnemonic = "movaps";
                if (cursor < maxLen) {
                    uint8_t m = code[cursor++];
                    uint8_t regIdx = ((m >> 3) & 7) | (rexR ? 8 : 0);
                    auto p = decode_modrm_mem(m, 16);
                    std::string xmmReg = "xmm" + std::to_string(regIdx);
                    if (op2 == 0x28) inst.operands = xmmReg + ", " + p.second;
                    else inst.operands = p.second + ", " + xmmReg;
                }
            }
            else if (op2 == 0x10 || op2 == 0x11) { // MOVUPS / MOVSS / MOVSD
                std::string mn = "movups";
                if (prefixStr.find("repne ") != std::string::npos) mn = "movsd";
                else if (prefixStr.find("rep ") != std::string::npos) mn = "movss";
                inst.mnemonic = mn;
                if (cursor < maxLen) {
                    uint8_t m = code[cursor++];
                    uint8_t regIdx = ((m >> 3) & 7) | (rexR ? 8 : 0);
                    auto p = decode_modrm_mem(m, (mn == "movups" ? 16 : 8));
                    std::string xmmReg = "xmm" + std::to_string(regIdx);
                    if (op2 == 0x10) inst.operands = xmmReg + ", " + p.second;
                    else inst.operands = p.second + ", " + xmmReg;
                }
            }
            else if (op2 == 0x57) { // XORPS
                inst.mnemonic = "xorps";
                if (cursor < maxLen) {
                    uint8_t m = code[cursor++];
                    uint8_t regIdx = ((m >> 3) & 7) | (rexR ? 8 : 0);
                    auto p = decode_modrm_mem(m, 16);
                    std::string xmmReg = "xmm" + std::to_string(regIdx);
                    inst.operands = xmmReg + ", " + p.second;
                }
            }
            else {
                inst.mnemonic = "db 0x0f, 0x" + hex_byte(op2);
            }
            inst.length = cursor;
            inst.bytes.assign(code, code + cursor);
            return inst;
        }

        // Single-byte Opcodes
        // PUSH reg (0x50 - 0x57)
        if (op >= 0x50 && op <= 0x57) {
            inst.mnemonic = "push";
            inst.operands = get_reg_name((op - 0x50) | (rexB ? 8 : 0), 8);
        }
        // POP reg (0x58 - 0x5F)
        else if (op >= 0x58 && op <= 0x5F) {
            inst.mnemonic = "pop";
            inst.operands = get_reg_name((op - 0x58) | (rexB ? 8 : 0), 8);
        }
        // MOV reg, imm32/imm64 (0xB8 - 0xBF)
        else if (op >= 0xB8 && op <= 0xBF) {
            inst.mnemonic = (defOpSize == 8) ? "movabs" : "mov";
            std::string r = get_reg_name((op - 0xB8) | (rexB ? 8 : 0), defOpSize);
            if (defOpSize == 8 && cursor + 8 <= maxLen) {
                uint64_t imm = *reinterpret_cast<const uint64_t*>(&code[cursor]);
                cursor += 8;
                inst.operands = r + ", 0x" + to_hex(imm);
            } else if (cursor + 4 <= maxLen) {
                uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                cursor += 4;
                inst.operands = r + ", 0x" + to_hex(imm);
            }
        }
        // MOV reg8, imm8 (0xB0 - 0xB7)
        else if (op >= 0xB0 && op <= 0xB7) {
            inst.mnemonic = "mov";
            std::string r = get_reg_name((op - 0xB0) | (rexB ? 8 : 0), 1);
            if (cursor < maxLen) {
                inst.operands = r + ", 0x" + hex_byte(code[cursor++]);
            }
        }
        // Jcc short rel8 (0x70 - 0x7F)
        else if (op >= 0x70 && op <= 0x7F) {
            static const char* jccs[] = {"jo","jno","jb","jae","je","jne","jbe","ja","js","jns","jp","jnp","jl","jge","jle","jg"};
            inst.mnemonic = jccs[op - 0x70];
            inst.isBranch = true;
            if (cursor < maxLen) {
                int8_t rel = static_cast<int8_t>(code[cursor++]);
                inst.targetAddress = rip + cursor + rel;
                inst.operands = "0x" + to_hex(inst.targetAddress);
            }
        }
        // JMP short rel8 (0xEB)
        else if (op == 0xEB) {
            inst.mnemonic = "jmp";
            inst.isBranch = true;
            if (cursor < maxLen) {
                int8_t rel = static_cast<int8_t>(code[cursor++]);
                inst.targetAddress = rip + cursor + rel;
                inst.operands = "0x" + to_hex(inst.targetAddress);
            }
        }
        // JMP rel32 (0xE9)
        else if (op == 0xE9) {
            inst.mnemonic = "jmp";
            inst.isBranch = true;
            if (cursor + 4 <= maxLen) {
                int32_t rel = *reinterpret_cast<const int32_t*>(&code[cursor]);
                cursor += 4;
                inst.targetAddress = rip + cursor + rel;
                inst.operands = "0x" + to_hex(inst.targetAddress);
            }
        }
        // CALL rel32 (0xE8)
        else if (op == 0xE8) {
            inst.mnemonic = "call";
            inst.isCall = true;
            if (cursor + 4 <= maxLen) {
                int32_t rel = *reinterpret_cast<const int32_t*>(&code[cursor]);
                cursor += 4;
                inst.targetAddress = rip + cursor + rel;
                inst.operands = "0x" + to_hex(inst.targetAddress);
            }
        }
        // RET (0xC3), RET imm16 (0xC2)
        else if (op == 0xC3) {
            inst.mnemonic = "ret";
            inst.isRet = true;
        }
        else if (op == 0xC2) {
            inst.mnemonic = "ret";
            inst.isRet = true;
            if (cursor + 2 <= maxLen) {
                uint16_t imm = *reinterpret_cast<const uint16_t*>(&code[cursor]);
                cursor += 2;
                inst.operands = "0x" + to_hex(imm);
            }
        }
        // LEA (0x8D)
        else if (op == 0x8D) {
            inst.mnemonic = "lea";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.first + ", " + p.second;
            }
        }
        // MOV r/m, r (0x89) or MOV r, r/m (0x8B)
        else if (op == 0x89) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.second + ", " + p.first;
            }
        }
        else if (op == 0x8B) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.first + ", " + p.second;
            }
        }
        // MOV r/m8, r8 (0x88) or MOV r8, r/m8 (0x8A)
        else if (op == 0x88) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], 1);
                inst.operands = p.second + ", " + p.first;
            }
        }
        else if (op == 0x8A) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], 1);
                inst.operands = p.first + ", " + p.second;
            }
        }
        // MOV r/m, imm32 (0xC7)
        else if (op == 0xC7) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                if (cursor + 4 <= maxLen) {
                    uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                    cursor += 4;
                    inst.operands = p.second + ", 0x" + to_hex(imm);
                }
            }
        }
        // MOV r/m8, imm8 (0xC6)
        else if (op == 0xC6) {
            inst.mnemonic = "mov";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], 1);
                if (cursor < maxLen) {
                    inst.operands = p.second + ", 0x" + hex_byte(code[cursor++]);
                }
            }
        }
        // Arithmetic / Logic rm/r (0x01, 0x09, 0x21, 0x29, 0x31, 0x39)
        else if (op == 0x01 || op == 0x09 || op == 0x21 || op == 0x29 || op == 0x31 || op == 0x39) {
            static const char* ops[] = {"add", "or", "and", "sub", "xor", "cmp"};
            int idx = (op == 0x01) ? 0 : (op == 0x09 ? 1 : (op == 0x21 ? 2 : (op == 0x29 ? 3 : (op == 0x31 ? 4 : 5))));
            inst.mnemonic = ops[idx];
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.second + ", " + p.first;
            }
        }
        // Arithmetic / Logic r/rm (0x03, 0x0B, 0x23, 0x2B, 0x33, 0x3B)
        else if (op == 0x03 || op == 0x0B || op == 0x23 || op == 0x2B || op == 0x33 || op == 0x3B) {
            static const char* ops[] = {"add", "or", "and", "sub", "xor", "cmp"};
            int idx = (op == 0x03) ? 0 : (op == 0x0B ? 1 : (op == 0x23 ? 2 : (op == 0x2B ? 3 : (op == 0x33 ? 4 : 5))));
            inst.mnemonic = ops[idx];
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.first + ", " + p.second;
            }
        }
        // Group 1: 0x81, 0x83 (ADD, OR, ADC, SBB, AND, SUB, XOR, CMP rm, imm)
        else if (op == 0x81 || op == 0x83) {
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                static const char* g1[] = {"add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"};
                inst.mnemonic = g1[g];
                auto p = decode_modrm_mem(m, defOpSize);
                if (op == 0x83 && cursor < maxLen) {
                    int8_t imm = static_cast<int8_t>(code[cursor++]);
                    inst.operands = p.second + ", 0x" + hex_byte(static_cast<uint8_t>(imm));
                } else if (op == 0x81 && cursor + 4 <= maxLen) {
                    uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                    cursor += 4;
                    inst.operands = p.second + ", 0x" + to_hex(imm);
                }
            }
        }
        // MOVSXD (0x63)
        else if (op == 0x63) {
            inst.mnemonic = "movsxd";
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                auto p = decode_modrm_mem(m, 4);
                uint8_t dstReg = ((m >> 3) & 7) | (rexR ? 8 : 0);
                inst.operands = get_reg_name(dstReg, 8) + ", " + p.second;
            }
        }
        // TEST r/m8, r8 (0x84)
        else if (op == 0x84) {
            inst.mnemonic = "test";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], 1);
                inst.operands = p.second + ", " + p.first;
            }
        }
        // TEST r/m, r (0x85)
        else if (op == 0x85) {
            inst.mnemonic = "test";
            if (cursor < maxLen) {
                auto p = decode_modrm_mem(code[cursor++], defOpSize);
                inst.operands = p.second + ", " + p.first;
            }
        }
        // Group 2 shifts: 0xC0, 0xC1 (rm, imm8)
        else if (op == 0xC0 || op == 0xC1) {
            int sz = (op == 0xC0) ? 1 : defOpSize;
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                static const char* g2[] = {"rol", "ror", "rcl", "rcr", "shl", "shr", "sal", "sar"};
                inst.mnemonic = g2[g];
                auto p = decode_modrm_mem(m, sz);
                if (cursor < maxLen) {
                    inst.operands = p.second + ", 0x" + hex_byte(code[cursor++]);
                }
            }
        }
        // Group 2 shifts: 0xD0, 0xD1 (by 1)
        else if (op == 0xD0 || op == 0xD1) {
            int sz = (op == 0xD0) ? 1 : defOpSize;
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                static const char* g2[] = {"rol", "ror", "rcl", "rcr", "shl", "shr", "sal", "sar"};
                inst.mnemonic = g2[g];
                auto p = decode_modrm_mem(m, sz);
                inst.operands = p.second + ", 1";
            }
        }
        // Group 2 shifts: 0xD2, 0xD3 (by cl)
        else if (op == 0xD2 || op == 0xD3) {
            int sz = (op == 0xD2) ? 1 : defOpSize;
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                static const char* g2[] = {"rol", "ror", "rcl", "rcr", "shl", "shr", "sal", "sar"};
                inst.mnemonic = g2[g];
                auto p = decode_modrm_mem(m, sz);
                inst.operands = p.second + ", cl";
            }
        }
        // Group 3: 0xF6, 0xF7 (test, not, neg, mul, imul, div, idiv)
        else if (op == 0xF6 || op == 0xF7) {
            int sz = (op == 0xF6) ? 1 : defOpSize;
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                static const char* g3[] = {"test", "test", "not", "neg", "mul", "imul", "div", "idiv"};
                inst.mnemonic = g3[g];
                auto p = decode_modrm_mem(m, sz);
                if (g == 0 || g == 1) { // test rm, imm
                    if (sz == 1 && cursor < maxLen) {
                        inst.operands = p.second + ", 0x" + hex_byte(code[cursor++]);
                    } else if (cursor + 4 <= maxLen) {
                        uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                        cursor += 4;
                        inst.operands = p.second + ", 0x" + to_hex(imm);
                    }
                } else {
                    inst.operands = p.second;
                }
            }
        }
        // TEST (e/r)ax, imm32 (0xA9)
        else if (op == 0xA9) {
            inst.mnemonic = "test";
            if (cursor + 4 <= maxLen) {
                uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                cursor += 4;
                inst.operands = get_reg_name(0, defOpSize) + ", 0x" + to_hex(imm);
            }
        }
        // NOP (0x90) / PAUSE (F3 90)
        else if (op == 0x90) {
            inst.mnemonic = (prefixStr.find("rep") != std::string::npos) ? "pause" : "nop";
        }
        // INT 3 (0xCC)
        else if (op == 0xCC) {
            inst.mnemonic = "int3";
        }
        // PUSH imm8 (0x6A)
        else if (op == 0x6A) {
            inst.mnemonic = "push";
            if (cursor < maxLen) {
                inst.operands = "0x" + hex_byte(code[cursor++]);
            }
        }
        // PUSH imm32 (0x68)
        else if (op == 0x68) {
            inst.mnemonic = "push";
            if (cursor + 4 <= maxLen) {
                uint32_t imm = *reinterpret_cast<const uint32_t*>(&code[cursor]);
                cursor += 4;
                inst.operands = "0x" + to_hex(imm);
            }
        }
        // Group 5: 0xFF (INC, DEC, CALL rm, JMP rm, PUSH rm)
        else if (op == 0xFF) {
            if (cursor < maxLen) {
                uint8_t m = code[cursor++];
                int g = (m >> 3) & 7;
                auto p = decode_modrm_mem(m, 8);
                if (g == 0) { inst.mnemonic = "inc"; inst.operands = p.second; }
                else if (g == 1) { inst.mnemonic = "dec"; inst.operands = p.second; }
                else if (g == 2) { inst.mnemonic = "call"; inst.isCall = true; inst.operands = p.second; }
                else if (g == 4) { inst.mnemonic = "jmp"; inst.isBranch = true; inst.operands = p.second; }
                else if (g == 6) { inst.mnemonic = "push"; inst.operands = p.second; }
                else { inst.mnemonic = "db 0xff"; }
            }
        }
        // LEAVE (0xC9)
        else if (op == 0xC9) {
            inst.mnemonic = "leave";
        }
        // Fallback for unhandled byte: define byte
        else {
            inst.mnemonic = "db";
            inst.operands = "0x" + hex_byte(op);
        }

        if (!prefixStr.empty() && inst.mnemonic != "pause" && inst.mnemonic != "nop") {
            inst.mnemonic = prefixStr + inst.mnemonic;
        }

        inst.length = cursor;
        inst.bytes.assign(code, code + cursor);
        return inst;
    }

private:
    static std::string hex_byte(uint8_t b) {
        char buf[4];
        std::snprintf(buf, sizeof(buf), "%02X", b);
        return buf;
    }

    static std::string to_hex(uint64_t val) {
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%llX", static_cast<unsigned long long>(val));
        return buf;
    }

    static std::string to_hex_padded(uint64_t val, int width) {
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%0*llX", width, static_cast<unsigned long long>(val));
        return buf;
    }
};

// ============================================================================
// Interactive Windows PE Live Debugger (Win32 Debug API)
// ============================================================================
class LiveDebugger {
public:
    PROCESS_INFORMATION pi{};
    STARTUPINFOA si{};
    bool isRunning = false;
    bool isAttached = false;
    DEBUG_EVENT lastEvent{};
    CONTEXT ctx{};
    std::string statusMsg = "";
    std::string targetPath = "";

    bool launch(const std::string& path) {
        targetPath = path;
        std::memset(&si, 0, sizeof(si));
        si.cb = sizeof(si);
        std::memset(&pi, 0, sizeof(pi));

        BOOL success = CreateProcessA(
            path.c_str(),
            nullptr,
            nullptr,
            nullptr,
            FALSE,
            DEBUG_ONLY_THIS_PROCESS | CREATE_NEW_CONSOLE,
            nullptr,
            nullptr,
            &si,
            &pi
        );

        if (!success) {
            statusMsg = "Failed to launch process: error " + std::to_string(GetLastError());
            return false;
        }

        isRunning = true;
        isAttached = true;
        statusMsg = "Process launched in DEBUG mode (PID: " + std::to_string(pi.dwProcessId) + ")";
        
        // Advance to initial breakpoint
        pump_events_until_break();
        refresh_context();
        return true;
    }

    void pump_events_until_break() {
        while (isRunning) {
            if (!WaitForDebugEvent(&lastEvent, 500)) {
                break;
            }

            if (lastEvent.dwDebugEventCode == EXCEPTION_DEBUG_EVENT) {
                DWORD code = lastEvent.u.Exception.ExceptionRecord.ExceptionCode;
                if (code == EXCEPTION_BREAKPOINT || code == EXCEPTION_SINGLE_STEP) {
                    statusMsg = (code == EXCEPTION_BREAKPOINT) ? "Hit Breakpoint" : "Single-step trapped";
                    break; // Stopped at break/step!
                }
            } else if (lastEvent.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) {
                statusMsg = "Process Exited with code " + std::to_string(lastEvent.u.ExitProcess.dwExitCode);
                isRunning = false;
                ContinueDebugEvent(lastEvent.dwProcessId, lastEvent.dwThreadId, DBG_CONTINUE);
                break;
            }

            ContinueDebugEvent(lastEvent.dwProcessId, lastEvent.dwThreadId, DBG_CONTINUE);
        }
    }

    void refresh_context() {
        if (!isRunning) return;
        ctx.ContextFlags = CONTEXT_FULL;
        GetThreadContext(pi.hThread, &ctx);
    }

    void step_into() {
        if (!isRunning) return;
        refresh_context();
        ctx.EFlags |= 0x100; // Set Trap Flag (TF) for single step
        SetThreadContext(pi.hThread, &ctx);

        ContinueDebugEvent(lastEvent.dwProcessId, lastEvent.dwThreadId, DBG_CONTINUE);
        pump_events_until_break();
        refresh_context();
    }

    void continue_exec() {
        if (!isRunning) return;
        ContinueDebugEvent(lastEvent.dwProcessId, lastEvent.dwThreadId, DBG_CONTINUE);
        pump_events_until_break();
        refresh_context();
    }

    void terminate() {
        if (isRunning && pi.hProcess) {
            TerminateProcess(pi.hProcess, 0);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
        }
        isRunning = false;
        statusMsg = "Debugger session terminated.";
    }

    std::vector<uint8_t> read_memory(uint64_t addr, size_t len) {
        std::vector<uint8_t> buf(len, 0);
        if (!isRunning || !pi.hProcess) return buf;
        SIZE_T read = 0;
        ReadProcessMemory(pi.hProcess, reinterpret_cast<LPCVOID>(addr), buf.data(), len, &read);
        buf.resize(read);
        return buf;
    }
};

// ============================================================================
// Interactive TUI Controller & State
// ============================================================================
enum class ViewMode {
    Hex,
    Disassembly,
    Split,
    Headers,
    LiveDebug,
    Help
};

class XBugApp {
public:
    BinaryFile file;
    LiveDebugger dbg;
    ViewMode mode = ViewMode::Hex;
    ViewMode prevMode = ViewMode::Hex;

    uint64_t cursorOffset = 0;
    uint64_t scrollOffset = 0;
    int bytesPerRow = 16;
    bool showBitInspector = true;
    std::string searchQuery = "";
    std::string statusNotice = "Ready. Press [?] for keybindings.";

    XBugApp(const std::string& path) {
        if (!file.load(path)) {
            std::cerr << "Failed to open file: " << path << "\n";
            std::exit(1);
        }
        if (file.meta.entryPointRaw != 0) {
            cursorOffset = file.meta.entryPointRaw;
            scrollOffset = (cursorOffset / 16) * 16;
            statusNotice = "Loaded executable. Jumped to Entry Point!";
        }
    }

    void run() {
        Term::init();
        bool running = true;

        while (running) {
            render();
            KeyEvent evt = read_key();

            if (evt.code == KeyCode::Escape || (evt.code == KeyCode::Char && (evt.ch == 'q' || evt.ch == 'Q'))) {
                if (mode == ViewMode::Help) {
                    mode = prevMode;
                } else if (mode == ViewMode::LiveDebug) {
                    dbg.terminate();
                    mode = prevMode;
                } else {
                    running = false;
                }
                continue;
            }

            handle_input(evt);
        }

        dbg.terminate();
        Term::restore();
    }

private:
    void handle_input(const KeyEvent& evt) {
        int termW, termH;
        Term::get_size(termW, termH);
        int viewRows = std::max(10, termH - 6);

        if (evt.code == KeyCode::Char) {
            char c = evt.ch;
            switch (c) {
                case 'h': case 'H': mode = ViewMode::Hex; break;
                case 'a': case 'A': mode = ViewMode::Disassembly; break;
                case 's': case 'S': mode = ViewMode::Split; break;
                case 'p': case 'P': mode = ViewMode::Headers; break;
                case 'b': case 'B': showBitInspector = !showBitInspector; break;
                case '?':
                    prevMode = mode;
                    mode = ViewMode::Help;
                    break;
                case 'e': case 'E':
                    if (file.meta.entryPointRaw != 0) {
                        cursorOffset = file.meta.entryPointRaw;
                        scrollOffset = (cursorOffset / bytesPerRow) * bytesPerRow;
                        statusNotice = "Jumped to Executable Entry Point!";
                    } else {
                        statusNotice = "No entry point found for raw file.";
                    }
                    break;
                case 'g': case 'G': prompt_goto(); break;
                case '/': prompt_search(); break;
                case 'n': case 'N': search_next(); break;
                case 'r': case 'R':
                    if (file.meta.format == FileFormatType::PE32 || file.meta.format == FileFormatType::PE64) {
                        prevMode = mode;
                        mode = ViewMode::LiveDebug;
                        if (!dbg.isRunning) {
                            dbg.launch(file.filePath);
                        }
                    } else {
                        statusNotice = "Only Windows PE executables (.exe) can be live-debugged.";
                    }
                    break;
                default: break;
            }
        }

        // Live Debugger Specific Keys
        if (mode == ViewMode::LiveDebug) {
            if (evt.code == KeyCode::F7 || (evt.code == KeyCode::Char && (evt.ch == 't' || evt.ch == 'T'))) {
                dbg.step_into();
            } else if (evt.code == KeyCode::F9 || (evt.code == KeyCode::Char && (evt.ch == 'c' || evt.ch == 'C'))) {
                dbg.continue_exec();
            } else if (evt.code == KeyCode::Char && (evt.ch == 'k' || evt.ch == 'K')) {
                dbg.terminate();
            }
            return;
        }

        // Arrow and Page Navigation
        uint64_t maxOffset = file.size() > 0 ? file.size() - 1 : 0;
        switch (evt.code) {
            case KeyCode::Up:
                if (cursorOffset >= static_cast<uint64_t>(bytesPerRow)) {
                    cursorOffset -= bytesPerRow;
                } else {
                    cursorOffset = 0;
                }
                break;
            case KeyCode::Down:
                if (cursorOffset + bytesPerRow <= maxOffset) {
                    cursorOffset += bytesPerRow;
                }
                break;
            case KeyCode::Left:
                if (cursorOffset > 0) cursorOffset--;
                break;
            case KeyCode::Right:
                if (cursorOffset < maxOffset) cursorOffset++;
                break;
            case KeyCode::PageUp:
                if (cursorOffset >= static_cast<uint64_t>(bytesPerRow * viewRows)) {
                    cursorOffset -= bytesPerRow * viewRows;
                } else {
                    cursorOffset = 0;
                }
                break;
            case KeyCode::PageDown:
                if (cursorOffset + bytesPerRow * viewRows <= maxOffset) {
                    cursorOffset += bytesPerRow * viewRows;
                } else {
                    cursorOffset = maxOffset;
                }
                break;
            case KeyCode::Home:
                cursorOffset = 0;
                break;
            case KeyCode::End:
                cursorOffset = maxOffset;
                break;
            default: break;
        }

        // Adjust scroll view to ensure cursor is visible
        if (cursorOffset < scrollOffset) {
            scrollOffset = (cursorOffset / bytesPerRow) * bytesPerRow;
        } else if (cursorOffset >= scrollOffset + bytesPerRow * viewRows) {
            scrollOffset = ((cursorOffset / bytesPerRow) - viewRows + 1) * bytesPerRow;
        }
    }

    void prompt_goto() {
        Term::restore();
        std::cout << "\n" << Term::FG_MNEMONIC << "Goto Offset (hex like 0x1000 or dec like 4096): " << Term::RESET;
        std::string input;
        std::getline(std::cin, input);
        if (!input.empty()) {
            try {
                uint64_t off = 0;
                if (input.rfind("0x", 0) == 0 || input.rfind("0X", 0) == 0) {
                    off = std::stoull(input, nullptr, 16);
                } else {
                    off = std::stoull(input, nullptr, 10);
                }
                if (off < file.size()) {
                    cursorOffset = off;
                    scrollOffset = (cursorOffset / bytesPerRow) * bytesPerRow;
                    statusNotice = "Jumped to offset 0x" + to_hex(off);
                } else {
                    statusNotice = "Offset out of range!";
                }
            } catch (...) {
                statusNotice = "Invalid offset entered.";
            }
        }
        Term::init();
    }

    void prompt_search() {
        Term::restore();
        std::cout << "\n" << Term::FG_MNEMONIC << "Search ASCII text or hex pattern (e.g., 'MZ' or '48 89 e5'): " << Term::RESET;
        std::getline(std::cin, searchQuery);
        Term::init();
        if (!searchQuery.empty()) {
            search_next();
        }
    }

    void search_next() {
        if (searchQuery.empty()) return;
        // Search as ASCII first
        std::string s = searchQuery;
        size_t start = cursorOffset + 1;
        if (start >= file.size()) start = 0;

        auto it = std::search(
            file.data.begin() + start, file.data.end(),
            s.begin(), s.end()
        );

        if (it != file.data.end()) {
            cursorOffset = std::distance(file.data.begin(), it);
            scrollOffset = (cursorOffset / bytesPerRow) * bytesPerRow;
            statusNotice = "Found match at 0x" + to_hex(cursorOffset);
        } else {
            statusNotice = "Pattern not found.";
        }
    }

    void render() {
        int w, h;
        Term::get_size(w, h);
        Term::move_cursor(1, 1);

        std::ostringstream buf;
        render_top_bar(buf, w);

        int viewHeight = h - 4;
        if (showBitInspector && (mode == ViewMode::Hex || mode == ViewMode::Split)) {
            viewHeight -= 3;
        }

        switch (mode) {
            case ViewMode::Hex:
                render_hex_view(buf, w, viewHeight);
                break;
            case ViewMode::Disassembly:
                render_disasm_view(buf, w, viewHeight);
                break;
            case ViewMode::Split:
                render_split_view(buf, w, viewHeight);
                break;
            case ViewMode::Headers:
                render_headers_view(buf, w, viewHeight);
                break;
            case ViewMode::LiveDebug:
                render_debug_view(buf, w, viewHeight);
                break;
            case ViewMode::Help:
                render_help_view(buf, w, viewHeight);
                break;
        }

        if (showBitInspector && (mode == ViewMode::Hex || mode == ViewMode::Split)) {
            render_bit_inspector(buf, w);
        }

        render_bottom_bar(buf, w);
        std::cout << buf.str();
        std::cout.flush();
    }

    void render_top_bar(std::ostringstream& out, int width) {
        std::string modeStr = "HEX VIEW";
        if (mode == ViewMode::Disassembly) modeStr = "DISASSEMBLY VIEW";
        else if (mode == ViewMode::Split) modeStr = "SPLIT VIEW (HEX + ASM)";
        else if (mode == ViewMode::Headers) modeStr = "PE/ELF HEADERS";
        else if (mode == ViewMode::LiveDebug) modeStr = "LIVE PROCESS DEBUGGER";
        else if (mode == ViewMode::Help) modeStr = "KEYBOARD HELP";

        std::string title = " X-BUG v1.0 [ " + file.filePath + " ] (" + file.meta.formatName + " | " + file.meta.arch + ") | " + modeStr;
        if (static_cast<int>(title.size()) > width) {
            title = title.substr(0, width);
        }

        out << Term::FG_BG_BAR << title;
        for (int i = title.size(); i < width; ++i) out << " ";
        out << Term::RESET << "\n";
    }

    void render_hex_view(std::ostringstream& out, int width, int rows) {
        for (int r = 0; r < rows; ++r) {
            uint64_t rowOffset = scrollOffset + r * bytesPerRow;
            if (rowOffset >= file.size()) {
                out << Term::FG_BORDER << "~" << Term::RESET << "\n";
                continue;
            }

            // Offset
            out << Term::FG_ADDR << to_hex_padded(rowOffset, 8) << Term::RESET << "  ";

            // Hex Bytes
            for (int b = 0; b < bytesPerRow; ++b) {
                uint64_t byteOffset = rowOffset + b;
                if (b == 8) out << " ";

                if (byteOffset < file.size()) {
                    uint8_t byteVal = file.get(byteOffset);
                    bool isCursor = (byteOffset == cursorOffset);

                    if (isCursor) out << Term::BG_SELECT;
                    else color_for_byte(out, byteVal);

                    char hBuf[3];
                    std::snprintf(hBuf, sizeof(hBuf), "%02X", byteVal);
                    out << hBuf << Term::RESET << " ";
                } else {
                    out << "   ";
                }
            }

            out << Term::FG_BORDER << " |" << Term::RESET;

            // ASCII View
            for (int b = 0; b < bytesPerRow; ++b) {
                uint64_t byteOffset = rowOffset + b;
                if (byteOffset < file.size()) {
                    uint8_t byteVal = file.get(byteOffset);
                    bool isCursor = (byteOffset == cursorOffset);
                    if (isCursor) out << Term::BG_SELECT;

                    if (byteVal >= 32 && byteVal <= 126) {
                        out << Term::FG_ASCII << static_cast<char>(byteVal) << Term::RESET;
                    } else {
                        out << Term::FG_ZERO << "." << Term::RESET;
                    }
                } else {
                    out << " ";
                }
            }
            out << Term::FG_BORDER << "|" << Term::RESET << "\n";
        }
    }

    void render_disasm_view(std::ostringstream& out, int width, int rows) {
        uint64_t curr = scrollOffset;
        bool is64 = (file.meta.format == FileFormatType::PE64 || file.meta.format == FileFormatType::ELF64);

        for (int r = 0; r < rows; ++r) {
            if (curr >= file.size()) {
                out << Term::FG_BORDER << "~" << Term::RESET << "\n";
                continue;
            }

            size_t maxBytes = std::min<size_t>(15, file.size() - curr);
            uint64_t vAddr = file.meta.imageBase + file.meta.raw_to_rva(curr);
            DecodedInst inst = X86Disasm::decode(&file.data[curr], maxBytes, vAddr, is64);

            bool isCursorRow = (cursorOffset >= curr && cursorOffset < curr + inst.length);
            if (isCursorRow) out << Term::BG_CURSOR << " > " << Term::RESET;
            else out << "   ";

            // Address
            out << Term::FG_ADDR << "0x" << to_hex_padded(vAddr, 12) << Term::RESET << "  ";

            // Byte Hex Dump (up to 5 bytes)
            std::string byteStr = "";
            for (size_t i = 0; i < std::min<size_t>(inst.length, 5); ++i) {
                char h[4];
                std::snprintf(h, sizeof(h), "%02X ", inst.bytes[i]);
                byteStr += h;
            }
            out << Term::FG_MUTED << std::setw(16) << std::left << byteStr << Term::RESET << " ";

            // Mnemonic & Operands
            if (inst.isCall) out << Term::FG_CALL;
            else if (inst.isBranch) out << Term::FG_BRANCH;
            else out << Term::FG_MNEMONIC;

            out << std::setw(8) << std::left << inst.mnemonic << Term::RESET << " ";
            out << Term::FG_OPERAND << std::setw(28) << std::left << inst.operands << Term::RESET;

            if (!inst.comment.empty()) {
                out << Term::FG_COMMENT << " ; " << inst.comment << Term::RESET;
            } else if (inst.isBranch || inst.isCall) {
                const auto* sec = file.meta.find_section(file.meta.rva_to_raw(inst.targetAddress - file.meta.imageBase));
                if (sec) {
                    out << Term::FG_COMMENT << " ; " << sec->name << Term::RESET;
                }
            }

            out << "\n";
            curr += inst.length;
        }
    }

    void render_split_view(std::ostringstream& out, int width, int rows) {
        int leftW = 46;
        int rightW = width - leftW - 3;
        bool is64 = (file.meta.format == FileFormatType::PE64 || file.meta.format == FileFormatType::ELF64);

        uint64_t hexOff = scrollOffset;
        uint64_t asmOff = cursorOffset;

        for (int r = 0; r < rows; ++r) {
            uint64_t rowOff = hexOff + r * 8; // 8 bytes per row in split mode
            std::ostringstream lineL;
            if (rowOff < file.size()) {
                lineL << Term::FG_ADDR << to_hex_padded(rowOff, 6) << Term::RESET << " ";
                for (int b = 0; b < 8; ++b) {
                    uint64_t bo = rowOff + b;
                    if (bo < file.size()) {
                        uint8_t val = file.get(bo);
                        if (bo == cursorOffset) lineL << Term::BG_SELECT;
                        else color_for_byte(lineL, val);
                        char h[3];
                        std::snprintf(h, sizeof(h), "%02X", val);
                        lineL << h << Term::RESET << " ";
                    } else {
                        lineL << "   ";
                    }
                }
                lineL << Term::FG_BORDER << "|" << Term::RESET;
                for (int b = 0; b < 8; ++b) {
                    uint64_t bo = rowOff + b;
                    if (bo < file.size()) {
                        uint8_t val = file.get(bo);
                        if (val >= 32 && val <= 126) lineL << Term::FG_ASCII << static_cast<char>(val) << Term::RESET;
                        else lineL << Term::FG_ZERO << "." << Term::RESET;
                    }
                }
            }

            std::ostringstream lineR;
            if (asmOff < file.size()) {
                size_t maxBytes = std::min<size_t>(15, file.size() - asmOff);
                uint64_t vAddr = file.meta.imageBase + file.meta.raw_to_rva(asmOff);
                DecodedInst inst = X86Disasm::decode(&file.data[asmOff], maxBytes, vAddr, is64);

                if (inst.isCall) lineR << Term::FG_CALL;
                else if (inst.isBranch) lineR << Term::FG_BRANCH;
                else lineR << Term::FG_MNEMONIC;

                lineR << std::setw(7) << std::left << inst.mnemonic << Term::RESET << " ";
                lineR << Term::FG_OPERAND << inst.operands << Term::RESET;
                asmOff += inst.length;
            }

            out << std::setw(leftW) << std::left << lineL.str()
                << Term::FG_BORDER << " │ " << Term::RESET
                << lineR.str() << "\n";
        }
    }

    void render_headers_view(std::ostringstream& out, int width, int rows) {
        out << Term::FG_MNEMONIC << " [ EXECUTABLE HEADERS & SECTIONS SUMMARY ]\n" << Term::RESET;
        out << Term::FG_ADDR << " Format: " << Term::RESET << file.meta.formatName << "\n";
        out << Term::FG_ADDR << " Target Architecture: " << Term::RESET << file.meta.arch << "\n";
        out << Term::FG_ADDR << " Image Base: " << Term::RESET << "0x" << to_hex(file.meta.imageBase) << "\n";
        out << Term::FG_ADDR << " Entry Point RVA: " << Term::RESET << "0x" << to_hex(file.meta.entryPointRVA)
            << " (Raw File Offset: 0x" << to_hex(file.meta.entryPointRaw) << ")\n\n";

        out << Term::FG_BORDER << " ┌────┬──────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────┐\n";
        out << " │ #  │ Name     │ Virt Addr    │ Virt Size    │ Raw Offset   │ Raw Size     │ Flags  │\n";
        out << " ├────┼──────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤\n" << Term::RESET;

        for (size_t i = 0; i < file.meta.sections.size(); ++i) {
            const auto& sec = file.meta.sections[i];
            std::string flags = "";
            if (sec.isReadable) flags += "R";
            if (sec.isWritable) flags += "W";
            if (sec.isExecutable) flags += "X";

            out << " │ " << std::setw(2) << i << " │ "
                << Term::FG_ASCII << std::setw(8) << std::left << sec.name << Term::RESET << " │ 0x"
                << std::setw(10) << std::hex << sec.virtualAddress << " │ 0x"
                << std::setw(10) << std::hex << sec.virtualSize << " │ 0x"
                << std::setw(10) << std::hex << sec.rawOffset << " │ 0x"
                << std::setw(10) << std::hex << sec.rawSize << " │ "
                << Term::FG_BRANCH << std::setw(6) << flags << Term::RESET << " │\n";
        }
        out << Term::FG_BORDER << " └────┴──────────┴──────────────┴──────────────┴──────────────┴──────────────┴────────┘\n" << Term::RESET;
    }

    void render_debug_view(std::ostringstream& out, int width, int rows) {
        out << Term::FG_BRANCH << " [ LIVE RUNTIME DEBUGGER ACTIVE ] " << Term::RESET
            << dbg.statusMsg << "\n";

        if (!dbg.isRunning) {
            out << Term::FG_MUTED << "Process is not currently running. Press [R] to launch or [Esc] to exit.\n" << Term::RESET;
            return;
        }

        // Display Registers
        out << Term::FG_ADDR << " Registers (x86_64):\n" << Term::RESET;
        out << " RAX: " << Term::FG_MNEMONIC << "0x" << to_hex(dbg.ctx.Rax) << Term::RESET
            << "  RBX: 0x" << to_hex(dbg.ctx.Rbx)
            << "  RCX: 0x" << to_hex(dbg.ctx.Rcx)
            << "  RDX: 0x" << to_hex(dbg.ctx.Rdx) << "\n";
        out << " RSI: 0x" << to_hex(dbg.ctx.Rsi)
            << "  RDI: 0x" << to_hex(dbg.ctx.Rdi)
            << "  RBP: 0x" << to_hex(dbg.ctx.Rbp)
            << "  RSP: " << Term::FG_CALL << "0x" << to_hex(dbg.ctx.Rsp) << Term::RESET << "\n";
        out << " RIP: " << Term::FG_BRANCH << "0x" << to_hex(dbg.ctx.Rip) << Term::RESET
            << "  EFLAGS: [ 0x" << to_hex(dbg.ctx.EFlags) << " ]\n\n";

        // Disassemble instructions at current RIP
        out << Term::FG_ADDR << " Code stream at RIP:\n" << Term::RESET;
        auto mem = dbg.read_memory(dbg.ctx.Rip, 64);
        size_t off = 0;
        for (int i = 0; i < 5 && off < mem.size(); ++i) {
            uint64_t vAddr = dbg.ctx.Rip + off;
            DecodedInst inst = X86Disasm::decode(&mem[off], mem.size() - off, vAddr, true);
            if (i == 0) out << Term::BG_CURSOR << " => " << Term::RESET;
            else out << "    ";
            out << Term::FG_ADDR << "0x" << to_hex(vAddr) << Term::RESET << "  "
                << Term::FG_MNEMONIC << std::setw(8) << std::left << inst.mnemonic << Term::RESET << " "
                << Term::FG_OPERAND << inst.operands << Term::RESET << "\n";
            off += inst.length;
        }

        out << "\n" << Term::FG_BG_BAR << " [F7/T] Step Into   [F9/C] Continue   [K] Terminate Process   [Esc] Exit Debug " << Term::RESET << "\n";
    }

    void render_bit_inspector(std::ostringstream& out, int width) {
        if (cursorOffset >= file.size()) return;
        uint8_t byteVal = file.get(cursorOffset);

        uint16_t u16 = (cursorOffset + 2 <= file.size()) ? *reinterpret_cast<const uint16_t*>(&file.data[cursorOffset]) : 0;
        uint32_t u32 = (cursorOffset + 4 <= file.size()) ? *reinterpret_cast<const uint32_t*>(&file.data[cursorOffset]) : 0;
        uint64_t u64 = (cursorOffset + 8 <= file.size()) ? *reinterpret_cast<const uint64_t*>(&file.data[cursorOffset]) : 0;

        std::string bits = "0b";
        for (int i = 7; i >= 0; --i) {
            bits += ((byteVal >> i) & 1) ? "1" : "0";
            if (i == 4) bits += " ";
        }

        const auto* sec = file.meta.find_section(cursorOffset);
        std::string secStr = sec ? ("Section: " + sec->name + (sec->isCode ? " [CODE]" : "")) : "Raw / Header";

        out << Term::FG_BORDER << "───[ Inspector: 0x" << to_hex(cursorOffset) << " ]───" << Term::RESET << "\n";
        out << " " << Term::FG_ADDR << "Bits: " << Term::FG_ASCII << bits << Term::RESET
            << " | u8: " << std::setw(3) << static_cast<int>(byteVal)
            << " | u16: 0x" << std::hex << u16
            << " | u32: 0x" << std::hex << u32
            << " | u64: 0x" << std::hex << u64
            << " | " << Term::FG_SPECIAL << secStr << Term::RESET << "\n";
    }

    void render_bottom_bar(std::ostringstream& out, int width) {
        double pct = (file.size() > 0) ? (static_cast<double>(cursorOffset) / file.size() * 100.0) : 0.0;
        std::ostringstream bar;
        bar << " [H]ex [A]sm [S]plit [P]E/ELF [B]its [G]oto [/]Find [E]ntry [R]un/Debug [?]Help [Q]uit | Off: 0x"
            << to_hex(cursorOffset) << " (" << std::fixed << std::setprecision(1) << pct << "%) | "
            << statusNotice;

        std::string barStr = bar.str();
        if (static_cast<int>(barStr.size()) > width) {
            barStr = barStr.substr(0, width);
        }
        out << Term::BG_STATUS << barStr;
        for (int i = barStr.size(); i < width; ++i) out << " ";
        out << Term::RESET;
    }

    void render_help_view(std::ostringstream& out, int width, int rows) {
        out << Term::FG_MNEMONIC << " [ X-BUG :: QUICK COMMAND REFERENCE ]\n\n" << Term::RESET;
        out << " Navigation:\n";
        out << "   Arrow Keys        : Move cursor 1 byte or 1 row\n";
        out << "   Page Up / Down    : Scroll one page\n";
        out << "   Home / End        : Jump to start / end of file\n";
        out << "   G / g             : Goto specific offset (hex 0x... or decimal)\n";
        out << "   E / e             : Jump directly to Executable Entry Point\n\n";

        out << " Views & Modes:\n";
        out << "   H / h             : Hex & ASCII viewer (with color-coded byte types)\n";
        out << "   A / a             : Disassembly viewer (Intel syntax x86/x64 decoder)\n";
        out << "   S / s             : Split dual view (Hex on left, Disassembly on right)\n";
        out << "   P / p             : Executable header inspector & Section Table\n";
        out << "   B / b             : Toggle bit / numeric value inspector panel\n\n";

        out << " Search & Debug:\n";
        out << "   /                 : Search ASCII text or byte pattern\n";
        out << "   N / n             : Find next search occurrence\n";
        out << "   R / r             : Launch target executable in Live Debugger mode\n";
        out << "   F7 / T (Debug)    : Single-step into instruction (sets Trap Flag)\n";
        out << "   F9 / C (Debug)    : Continue execution until next event\n";
        out << "   K (Debug)         : Terminate debugged process\n";
        out << "   Esc / Q           : Exit view or Quit\n\n";
        out << Term::FG_ASCII << " Press [Esc] or [Q] to return to previous view." << Term::RESET << "\n";
    }

    void color_for_byte(std::ostream& os, uint8_t b) {
        if (b == 0x00) os << Term::FG_ZERO;
        else if (b >= 32 && b <= 126) os << Term::FG_ASCII;
        else if (b == 0xFF) os << Term::FG_HIGH;
        else if (b == 0xCC || b == 0xC3) os << Term::FG_BRANCH;
        else os << Term::FG_SPECIAL;
    }

public:
    static std::string to_hex(uint64_t val) {
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%llX", static_cast<unsigned long long>(val));
        return buf;
    }

    static std::string to_hex_padded(uint64_t val, int width) {
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%0*llX", width, static_cast<unsigned long long>(val));
        return buf;
    }
};

// ============================================================================
// Entry Point
// ============================================================================
// Helper for non-interactive CLI modes
void print_cli_help(const char* prog) {
    std::cout << Term::FG_MNEMONIC << "X-BUG :: Advanced Standalone Low-Level Binary Debugger & Disassembler\n" << Term::RESET;
    std::cout << "Usage:\n";
    std::cout << "  " << prog << " <file>                     Launch interactive TUI debugger / hex & disasm screen\n";
    std::cout << "  " << prog << " --headers <file>           Display PE/ELF headers and section table\n";
    std::cout << "  " << prog << " --disasm <file> [cnt] [off] Disassemble [cnt] instructions from [off] or entry\n";
    std::cout << "  " << prog << " --hex <file> [off] [bytes]  Dump [bytes] in hex & ASCII starting from [off]\n";
    std::cout << "  " << prog << " --help                     Show this help reference\n";
}

int main(int argc, char* argv[]) {
    if (argc > 1) {
        std::string arg1 = argv[1];
        if (arg1 == "--help" || arg1 == "-h" || arg1 == "/?") {
            print_cli_help(argv[0]);
            return 0;
        }

        if (arg1 == "--headers") {
            if (argc < 3) {
                std::cerr << "Error: File path required for --headers\n";
                return 1;
            }
            BinaryFile bf;
            if (!bf.load(argv[2])) {
                std::cerr << "Failed to open file: " << argv[2] << "\n";
                return 1;
            }
            std::cout << Term::FG_MNEMONIC << "=== EXECUTABLE HEADERS & SECTIONS ===\n" << Term::RESET;
            std::cout << "File: " << argv[2] << " (" << bf.size() << " bytes)\n";
            std::cout << "Format: " << bf.meta.formatName << "\n";
            std::cout << "Architecture: " << bf.meta.arch << "\n";
            std::cout << "Image Base: 0x" << std::hex << bf.meta.imageBase << "\n";
            std::cout << "Entry Point RVA: 0x" << std::hex << bf.meta.entryPointRVA
                      << " (Raw Offset: 0x" << bf.meta.entryPointRaw << ")\n\n";

            std::cout << "Sections:\n";
            for (size_t i = 0; i < bf.meta.sections.size(); ++i) {
                const auto& s = bf.meta.sections[i];
                std::cout << "  [" << i << "] " << std::setw(8) << std::left << s.name
                          << " VirtAddr: 0x" << std::hex << std::setw(8) << s.virtualAddress
                          << " VirtSize: 0x" << std::hex << std::setw(8) << s.virtualSize
                          << " RawOff: 0x" << std::hex << std::setw(8) << s.rawOffset
                          << " RawSize: 0x" << std::hex << std::setw(8) << s.rawSize
                          << " Flags: " << (s.isReadable ? "R" : "-")
                                        << (s.isWritable ? "W" : "-")
                                        << (s.isExecutable ? "X" : "-") << "\n";
            }
            return 0;
        }

        if (arg1 == "--disasm") {
            if (argc < 3) {
                std::cerr << "Error: File path required for --disasm\n";
                return 1;
            }
            BinaryFile bf;
            if (!bf.load(argv[2])) {
                std::cerr << "Failed to open file: " << argv[2] << "\n";
                return 1;
            }
            size_t count = 30;
            if (argc > 3) count = std::stoull(argv[3]);
            uint64_t offset = (bf.meta.entryPointRaw != 0) ? bf.meta.entryPointRaw : 0;
            if (argc > 4) {
                std::string offStr = argv[4];
                offset = (offStr.rfind("0x", 0) == 0) ? std::stoull(offStr, nullptr, 16) : std::stoull(offStr);
            }

            bool is64 = (bf.meta.format == FileFormatType::PE64 || bf.meta.format == FileFormatType::ELF64);
            std::cout << Term::FG_MNEMONIC << "=== DISASSEMBLY (Starting from offset 0x" << std::hex << offset << ") ===\n" << Term::RESET;

            for (size_t i = 0; i < count && offset < bf.size(); ++i) {
                size_t maxBytes = std::min<size_t>(15, bf.size() - offset);
                uint64_t vAddr = bf.meta.imageBase + bf.meta.raw_to_rva(offset);
                DecodedInst inst = X86Disasm::decode(&bf.data[offset], maxBytes, vAddr, is64);

                std::string byteStr = "";
                for (size_t b = 0; b < std::min<size_t>(inst.length, 5); ++b) {
                    char h[4];
                    std::snprintf(h, sizeof(h), "%02X ", inst.bytes[b]);
                    byteStr += h;
                }

                std::cout << Term::FG_ADDR << "0x" << XBugApp::to_hex_padded(vAddr, 12) << Term::RESET << "  "
                          << Term::FG_MUTED << std::setw(16) << std::left << byteStr << Term::RESET << " "
                          << (inst.isCall ? Term::FG_CALL : (inst.isBranch ? Term::FG_BRANCH : Term::FG_MNEMONIC))
                          << std::setw(8) << std::left << inst.mnemonic << Term::RESET << " "
                          << Term::FG_OPERAND << std::setw(28) << std::left << inst.operands << Term::RESET;
                if (!inst.comment.empty()) {
                    std::cout << Term::FG_COMMENT << " ; " << inst.comment << Term::RESET;
                }
                std::cout << "\n";
                offset += inst.length;
            }
            return 0;
        }

        if (arg1 == "--hex") {
            if (argc < 3) {
                std::cerr << "Error: File path required for --hex\n";
                return 1;
            }
            BinaryFile bf;
            if (!bf.load(argv[2])) {
                std::cerr << "Failed to open file: " << argv[2] << "\n";
                return 1;
            }
            uint64_t offset = 0;
            size_t bytesToDump = 256;
            if (argc > 3) {
                std::string offStr = argv[3];
                offset = (offStr.rfind("0x", 0) == 0) ? std::stoull(offStr, nullptr, 16) : std::stoull(offStr);
            }
            if (argc > 4) bytesToDump = std::stoull(argv[4]);

            for (size_t row = 0; row < bytesToDump && offset + row < bf.size(); row += 16) {
                uint64_t ro = offset + row;
                std::cout << Term::FG_ADDR << XBugApp::to_hex_padded(ro, 8) << Term::RESET << "  ";
                for (int b = 0; b < 16; ++b) {
                    if (b == 8) std::cout << " ";
                    if (ro + b < bf.size()) {
                        char h[4];
                        std::snprintf(h, sizeof(h), "%02X ", bf.get(ro + b));
                        std::cout << h;
                    } else {
                        std::cout << "   ";
                    }
                }
                std::cout << " |";
                for (int b = 0; b < 16; ++b) {
                    if (ro + b < bf.size()) {
                        uint8_t c = bf.get(ro + b);
                        std::cout << ((c >= 32 && c <= 126) ? static_cast<char>(c) : '.');
                    }
                }
                std::cout << "|\n";
            }
            return 0;
        }
    }

    std::string targetFile = "";
    if (argc > 1) {
        targetFile = argv[1];
    } else {
        std::cout << Term::FG_MNEMONIC << "╔═══════════════════════════════════════════════════════════════════╗\n";
        std::cout << "║        X-BUG :: ADVANCED STANDALONE BINARY DEBUGGER & DISASM      ║\n";
        std::cout << "╚═══════════════════════════════════════════════════════════════════╝\n" << Term::RESET;
        std::cout << "Enter file path to inspect (or press Enter for 'hello.exe'): ";
        std::getline(std::cin, targetFile);
        if (targetFile.empty()) {
            targetFile = "hello.exe";
        }
    }

    XBugApp app(targetFile);
    app.run();
    return 0;
}
