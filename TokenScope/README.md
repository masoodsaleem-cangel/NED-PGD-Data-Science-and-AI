# TokenScope

A Windows C++ viewer for watching a local language model generate text. Each position in the timeline contains the token's final hidden state, the model's next-token probabilities, and the attention rows captured during that decode.

## Run it

1. Extract the ZIP into a folder.
2. Double-click **Start_Qwen.cmd** for a live run with `C:\qwen2.5-0.5b-instruct-q4_k_m.gguf`. The viewer opens while the model loads. Use **New run** to change the prompt or switch to Ornith.
3. Double-click **Replay.cmd** to explore the bundled Qwen recording. **Tour** animates all three views. **Preview.mp4** is a 12-second recording from the native renderer.

To patch the previously extracted project in `Documents\GitHub\TokenScope_Windows_x64\TokenScope`, close its viewer, extract this ZIP into a separate folder and double-click **Apply_Update.cmd** in that folder. The updater uses Python 3.9+ and checks the existing files before applying the update.

The Windows x64 executables and matching CPU and Vulkan runtime are in `bin`. Replay runs offline with an OpenGL 3.3 or newer display driver. The renderer uses OpenGL 4.5 when available. Compute particles use OpenGL 4.3 or later. The live worker uses the local GGUF you select.

## Read the answer or follow its path

The two switches below the canvas start **off** on launch and whenever you open a trace or start a run.

- **Thinking text** controls the text panel. With the switch off, it shows the original question in green and the generated answer in red. During a live run the answer grows as tokens arrive. Opening a recording shows its complete answer. Play, step or drag the timeline to watch the text appear at its recorded token positions. Switch on **Thinking text** to see the selected step and any text the model explicitly emitted inside `<think>` tags. If generation ends during thinking, the footer shows the reason.
- **Answer path** builds the Cosmos overlay on demand. Gold arrows connect the last prompt token to the first generated token, then the generated tokens in order. Entering from a prompt position jumps to the first answer token if one is already available. Step through or play to grow the trail. Switching off releases its cached edges and stops the overlay calculations.
- In **Inspect → Branches**, **Attention** shows up to three keys from the query that predicted the selected answer token, at the chosen layer and head. A blue ring marks attention to that query's own position. **Similar tokens** draws dotted links to the three earlier positions with the highest cosine similarity using their full contextual vectors. **None** leaves the chronological arrows. Both kinds of branches refer to positions in this run. Training examples have no recorded positions in the trace.

Click the three LEDs at the lower-left of Cosmos to filter the graph. **Prompt** (teal) and **Generated** (amber) show or hide their tokens, labels and attached links. **Layer path** (violet) controls the selected visible token's layer trajectory. A filled LED is on and an outlined LED is off. All three start on.

For a one-word answer, choose **Open** and select `examples/cashed-cheque.jsonl`. Qwen received “The cheque is cashed in a ___. Fill in the blank with one word.” and generated **bank**. The generation ends after that one token. For a longer trail, open `examples/two-banks.jsonl` and advance through **fish**, **swim**, **past**.

## Try the two uses of “bank”

The example prompt reads “I deposited cash at the bank. By the river, I sat on the bank and watched the”.

| In the replay | What to inspect |
| --- | --- |
| **Cosmos**, position **16** | Select the second “bank”. Position 6 has the same token ID, 6073. The dashed line connects the two positions. Their full 896-dimensional final hidden states have a cosine similarity of **0.764**. The first three principal components retain **50.24%** of the variation in the 19-token prompt. |
| **Loom**, position **19**, layer **10**, head **3** | The query is “the”. The ribbon to “watched” carries **29.3%** of this head's attention. Drag **Head** or **Layer** to see how the distribution changes. |
| **Race**, position **19** | “river” leads at **20.27%**. The sampler draws “fish”, whose original probability is **4.86%**. Toggle **Apply sampling temperature** to inspect the actual draw distribution. Advance one position to see “fish” enter the context. |

The example contains 19 prompt tokens and 24 generated tokens. It includes all 24 Qwen layers, all 14 heads and the full final hidden vectors. The positions shown in the interface start at 1. Layer and head numbers start at 0.

## Controls

| Action | Control |
| --- | --- |
| Play or pause, step, jump | Space, left/right arrows, timeline slider |
| Orbit or zoom | Right-drag, mouse wheel |
| Zoom in on a word in Cosmos | Double-click its dot or label, or press **F** for the selected token. Scroll for a closer view. |
| Center the three axes in Cosmos | **0** centers the origin at the current zoom. **Home** restores the overview. |
| Choose Cosmos, Loom or Race | 1, 2 or 3 |
| Inspect an earlier position | Click its point or key |
| Build or clear the answer trail | Answer path in the lower bar |
| Show or hide the token step and tagged thinking | Thinking text in the lower bar |
| Toggle the inspector or point labels | I or L |
| Hide the interface for a presentation | Tab |
| Toggle visual effects or reset the camera | E or Home |
| Save a completed capture, or reopen it | Save or Open |

The live view follows incoming tokens. Scrubbing lets you inspect earlier positions while generation continues. Use **Follow** to catch up. **Save** preserves the trace for replay.

## What the scenes measure

- **Embedding Cosmos** fits PCA once to L2-normalized final hidden states and fixes that basis for the run. The calibration normally uses the prompt. For prompts shorter than four tokens it includes up to four available positions. The three coordinates are projections. The inspector calculates cosine similarity from the full vectors when raw capture is enabled.
- **Layer path** follows one token through the model. Each violet dot is the recorded output of one layer (`l_out-N`) for that token, projected onto the same three PCA axes. Hover a dot to see its layer number. A fine line joins consecutive recorded layers and connects the last model layer to the token's final point when that layer was recorded. Missing layers leave gaps. Select **Loom** to see attention between tokens, or enable **Answer path** to connect the generated tokens in order.
- **Attention Loom** reads the post-softmax tensor for the selected query and displays its 12 strongest keys. The trace keeps all causal keys for every captured head. Ribbon width encodes weight. A layer without a validated tensor displays a status message. This can occur on a hybrid model's recurrent layers.
- **Logit Race** applies a stable softmax over the entire vocabulary. Its five displayed probabilities retain their full-vocabulary values. The raw distribution uses temperature 1. The sampling distribution uses your chosen temperature and the same full vocabulary. Zero temperature selects the largest logit. Each chart scales its vertical axis to its leader. Amber marks the next supplied prompt token during prefill and the actual draw during generation. If that token falls outside the top five it appears in an extra lane.

**Entropy** in the inspector measures how spread out the model's next-token probabilities are across its full vocabulary, before sampling temperature is applied. If one token has 100% of the probability, entropy is 0 bits. Two equally likely tokens give 1 bit. A model can strongly favor a factually wrong answer.

## Capture options

**New run** controls model, prompt, chat formatting, temperature, seed, length, GPU layers, raw vectors and layer paths. Capturing one attention layer reduces readback overhead. Select **Record all layers** for live layer switching during replay. To inspect a different layer in a single-layer recording, start a new capture. GPU layers of 0 selects CPU inference. The device label reports the offload count from llama.cpp. Its total can include the output layer.

New runs start in **Raw text** at temperature **1.0**, seed **42**, with a 32-token generation budget in the viewer. The tokenizer receives the text you typed and uses its normal beginning-of-sequence handling. The GGUF filename and metadata identify the model in the inspector. The model generates a continuation, so an input that ends in a question can naturally produce another question.

Choose **Chat (one user turn)** to test the same text as a conversation. For the two bundled-model presets this adds user and assistant turn markers. The assistant prefix defaults to **None**. On Ornith, **Open thinking block** and **Empty thinking block** let you explicitly compare those two prefixes. The **Thinking text** switch below the graph only changes what you see.

Open **Inspect** and expand **Model input** to see the prompt reconstructed from the actual decoded token pieces, including any control tokens. Expand **Token IDs** for the exact sequence sent to the decoder. Saved recordings show the input they originally used. At temperature **0** the sampler always picks the highest-scoring next token. At **1** it draws from the model's full next-token probability distribution.

The capture worker owns the model and performs one causal decode per position. It explicitly requests output for that token, enables embeddings, sets pooling to `NONE`, and reads the token's logits and final hidden state before the next decode. Attention capture disables flash attention and reads only matching `kq_soft_max-N` tensors. The callback checks shape, type, strides, causal key count, finite values and row sums. The GUI reads completed JSON Lines records while the worker runs.

Standard capture supports up to 128 prompt tokens and 256 generated tokens from the CLI. All-layer capture supports up to 96 total positions with an additional size bound based on the model's layer and head counts. Optional chat formatting passes one user message to llama.cpp's built-in formatter for the GGUF's template.

### Print embedding dimensions and the top five

From PowerShell in the extracted folder, run

```powershell
.\bin\Capture.exe --model "C:\qwen2.5-0.5b-instruct-q4_k_m.gguf" --prompt "The capital of Pakistan is" --tokens 0
```

### Record a trace with full vectors

```powershell
.\bin\Capture.exe --model "C:\qwen2.5-0.5b-instruct-q4_k_m.gguf" --prompt "The sky above Karachi was" --tokens 20 --temperature 0.7 --seed 42 --layer 10 --raw --out karachi.jsonl
.\bin\TokenScope.exe --trace karachi.jsonl
```

Choose a fresh output filename for each CLI capture. Both the viewer and the worker default to raw text. Use `--chat` for one chat turn. On a supported model add `--model-thinking` or `--direct-answer` to supply the corresponding assistant prefix. Use `--all-layers` for a short full inspection or `--no-attention --no-paths` to capture final vectors and logits with less instrumentation. The worker's `--raw` option records full hidden vectors and is independent of input format.

### Check or plot PCA in Python

The viewer and capture worker run independently of Python. The plotting tool uses NumPy and Matplotlib. With those installed, run

```powershell
python tools\plot_trace.py examples\two-banks.jsonl --verify --output cosmos.png
```

The tool recomputes PCA with singular value decomposition and checks attention row sums and shapes. Use `--check-only` for numerical verification. The independent projection matched the included native recording to within **1.5 × 10⁻⁷** on all 43 positions.

## Build in Antigravity

Open the folder containing `CMakeLists.txt`. In CMake Tools, select the **Windows x64 Ninja Release** preset and your x64 compiler kit, then build. A second preset targets Visual Studio 2022 x64. The GLFW, Dear ImGui, GLAD and JSON sources are bundled, so the build can configure offline.

```powershell
cmake --preset ninja
cmake --build --preset ninja
.\build\ninja\bin\TokenScope.exe
```

CMake searches `C:\Program Files\llama.cpp` and the WinGet package directory. Point `LLAMA_ROOT` at another matching SDK when needed. For example

```powershell
cmake --preset ninja "-DLLAMA_ROOT=C:/Program Files/llama.cpp"
```

SDK builds link all import libraries found in the SDK library directory and copy all DLLs from its binary directory beside the capture executable. Current llama.cpp C APIs are required. For a runtime-only installation the included headers match **b10816 / 427291b5b**. For another runtime version, supply its matching headers and libraries. To compile just the viewer, configure with `-DTOKENSCOPE_CAPTURE=OFF`.

2. Visual Studio 2022 (open the folder)
Install Visual Studio 2022 with the Desktop development with C++ workload. Launch VS → Continue without code → File → Open → Folder… and pick the folder that contains CMakeLists.txt. VS uses its built-in CMake support (no separate CMake install needed) and reads the shipped CMakePresets.json automatically. Choose the Windows x64 Ninja Release preset — or the Visual Studio 2022 x64 preset — from the configuration dropdown in the toolbar, wait for CMake generation finished, then Build → Build All (Ctrl+Shift+B). Run TokenScope.exe from the output path shown in the status bar (for the Ninja preset that is build\ninja\bin\TokenScope.exe).

3. CMake GUI (configure + generate)
Install CMake from cmake.org or winget install Kitware.CMake. Open cmake-gui and set Where is the source code to the folder containing CMakeLists.txt and Where to build the binaries to a fresh build directory. Press Configure, pick Visual Studio 17 2022 with x64 (or Ninja if you have it on PATH), then press Generate. Click Open Project to launch the generated solution, set the configuration to Release and build. The binary ends up in build\Release\TokenScope.exe for the VS generator, or build\bin\TokenScope.exe for Ninja. With the Ninja generator you can also skip the GUI after generation and run cmake --build build from a Developer PowerShell.

CMake searches C:\Program Files\llama.cpp and the WinGet package directory. Point LLAMA_ROOT at another matching SDK when needed. For example

cmake --preset ninja "-DLLAMA_ROOT=C:/Program Files/llama.cpp"

SDK builds link all import libraries found in the SDK library directory and copy all DLLs from its binary directory beside the capture executable. Current llama.cpp C APIs are required. For a runtime-only installation the included headers match b10816 / 427291b5b. For another runtime version, supply its matching headers and libraries. To compile just the viewer, configure with -DTOKENSCOPE_CAPTURE=OFF.

### Source layout

| File | Responsibility |
| --- | --- |
| `src/capture.cpp` | GGUF loading, token-by-token decode, tensor probes and trace records |
| `src/sampling.hpp` | Full-vocabulary probabilities, entropy and seeded draws |
| `src/pca.hpp` | Fixed PCA basis and projection |
| `src/session.cpp` | Background capture process, live trace reader and replay |
| `src/renderer.cpp` | 3D geometry, GPU instancing, ribbons and compute particles |
| `src/answer.cpp` | On-demand answer trail, context links and displayed reply text |
| `src/viewer.cpp` | Window, inspection controls, camera and playback |

Verified on Windows x64 with CMake, Ninja and MinGW GCC 15.1. Qwen ran with Vulkan GPU offload on Intel UHD Graphics 620. Ornith was checked in a short CPU run with 4,096 output dimensions, 32 layers and 16 heads. All three scenes rendered on OpenGL 4.5.

Third-party source and runtime notices are in `vendor` and `bin`. The build uses GLFW 3.4, Dear ImGui 1.91.9b, generated GLAD 4.5 compatibility bindings and nlohmann/json 3.11.3. [llama.cpp C API](https://github.com/ggml-org/llama.cpp/blob/427291b5b/include/llama.h) · [Attention graph](https://github.com/ggml-org/llama.cpp/blob/427291b5b/src/llama-graph.cpp) · [GLFW](https://github.com/glfw/glfw/tree/3.4) · [Dear ImGui](https://github.com/ocornut/imgui/tree/v1.91.9b) · [GLAD bindings](https://github.com/JoeyDeVries/LearnOpenGL/tree/master/includes/glad) · [nlohmann/json](https://github.com/nlohmann/json/tree/v3.11.3)
