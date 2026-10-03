# X-BUG

A fast, standalone, low-level binary inspector, hex viewer, x86/x64 disassembler, and Windows process debugger written in modern C++ with **zero external dependencies**.

---

## Features

- **Universal File Loader**: Inspect any file (raw binary, images, executables, DLLs).
- **Format Auto-Detection**: Parses PE32, PE32+ (64-bit), and ELF headers, entry points, and section tables (`.text`, `.rdata`, `.data`).
- **Native x86/x64 Disassembler**: Built-in Intel syntax instruction decoder (handles REX prefixes, ModR/M, SIB, RIP-relative addressing, and SSE).
- **Multiple Views**:
  - **Hex View (`H`)**: 16-byte color-coded hex dump and ASCII screen.
  - **Disassembly View (`A`)**: Line-by-line machine code disassembly with branch targets and section annotations.
  - **Split View (`S`)**: Synchronized hex and disassembly panes side-by-side.
  - **PE/ELF Headers (`P`)**: Visual section table with permissions (`R-X`, `RW-`, `R--`).
  - **Bit Inspector (`B`)**: Live breakdown of selected byte (bits `0b...`, uint8, uint16, uint32, uint64).
- **Live Process Debugger (`R`)**: Launch and debug Windows PE executables with register inspection (`RAX`..`R15`, `RIP`, `EFLAGS`), memory disassembly at `RIP`, single-stepping (`F7`), and continue (`F9`).

---

## Build

Requires MinGW-w64 or any C++20 compliant compiler on Windows:

```powershell
g++ -std=c++20 -O3 x_bug.cpp -o x_bug.exe
```

---

## How to Use

### 1. Interactive TUI Mode
Run `x_bug.exe` with any target file:
```powershell
.\x_bug.exe target.exe
```
*(If run without arguments, it will prompt for a file path).*

### 2. Command-Line Options
You can also run X-BUG directly in your terminal for quick inspection and scripting:

```powershell
# Disassemble instructions from entry point (or custom offset)
.\x_bug.exe --disasm target.exe 30

# Dump hex & ASCII (offset 0, 64 bytes)
.\x_bug.exe --hex target.exe 0 64

# Inspect executable headers and section table
.\x_bug.exe --headers target.exe

# Show CLI help
.\x_bug.exe --help
```

---

## Keybindings (Interactive Mode)

| Key | Action |
| :--- | :--- |
| **`↑` / `↓` / `←` / `→`** | Move cursor byte-by-byte or row-by-row |
| **`PageUp` / `PageDown`** | Scroll one page up / down |
| **`Home` / `End`** | Jump to start / end of file |
| **`G`** | Goto offset (hex `0x1000` or dec `4096`) |
| **`E`** | Jump to executable Entry Point |
| **`/`** | Search text string or byte pattern |
| **`N`** | Find next match |
| **`H`** | Hex & ASCII View |
| **`A`** | Disassembly View |
| **`S`** | Split Dual View (Hex + Asm) |
| **`P`** | Executable Headers & Sections |
| **`B`** | Toggle Bit & Value Inspector |
| **`R`** | Launch Live Process Debugger (PE `.exe`) |
| **`F7` / `T`** | *Debug:* Step Into instruction |
| **`F9` / `C`** | *Debug:* Continue execution |
| **`K`** | *Debug:* Terminate debugged process |
| **`?`** | Help reference |
| **`Esc` / `Q`** | Back / Exit |

---

## License
MIT License. Standalone and open source.
