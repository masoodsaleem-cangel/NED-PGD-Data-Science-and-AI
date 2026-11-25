"""Plot a native capture and independently verify the projection with NumPy."""
import argparse
import json
from pathlib import Path

import numpy as np


def read_trace(path):
    with path.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]
    if len(records) < 3 or records[0].get("format") != "tokenscope/1":
        raise ValueError("Expected a TokenScope v1 trace.")
    header, frames, end = records[0], records[1:-1], records[-1]
    if end.get("event") != "end" or end["frames"] != len(frames):
        raise ValueError("The trace is incomplete.")
    return header, frames


def verify(header, frames):
    xyz = np.array([f["xyz"] for f in frames], dtype=float)
    for i, frame in enumerate(frames):
        if frame["index"] != i or frame["event"] != "token":
            raise ValueError(f"Unexpected frame order at {i}.")
        for rows in [frame["attention"], *(layer["heads"] for layer in frame.get("attention_layers", []))]:
            if not rows:
                continue
            weights = np.asarray(rows)
            if weights.shape != (header["heads"], i + 1):
                raise ValueError(f"Unexpected attention shape at {i}.")
            if not np.isfinite(weights).all() or weights.min() < 0 or not np.allclose(weights.sum(1), 1, atol=.004):
                raise ValueError(f"Invalid attention probabilities at {i}.")
        top = [v["p"] for v in frame["top"]]
        if top != sorted(top, reverse=True) or sum(top) > 1.00001 or min(top) < 0:
            raise ValueError(f"Invalid next-token distribution at {i}.")
    if not all("embedding" in f for f in frames):
        raise ValueError("Independent PCA needs a capture made with --raw.")
    data = np.asarray([f["embedding"] for f in frames], dtype=np.float64)
    if data.shape[1] != header["dims"] or not np.isfinite(data).all():
        raise ValueError("Invalid raw embedding matrix.")
    lengths = np.linalg.norm(data, axis=1, keepdims=True)
    x = data / np.where(lengths > 0, lengths, 1)
    n = header["fit_tokens"]
    x -= x[:n].mean(axis=0)
    _, singular, vt = np.linalg.svd(x[:n], full_matrices=False)
    power = singular**2
    rank = min(3, int((power > 1e-10 * max(1, power.sum())).sum()))
    ref = np.zeros_like(xyz)
    explained = np.zeros(3)
    if rank:
        ref[:, :rank] = x @ vt[:rank].T
        explained[:rank] = power[:rank] / power.sum()
        # Eigenvectors can differ in sign or orientation inside a tied eigenspace.
        u, _, v = np.linalg.svd(ref[:n].T @ xyz[:n])
        ref = ref @ (u @ v)
    deviation = np.abs(ref - xyz).max()
    if deviation > 3e-4 or not np.allclose(explained, header["variance"], atol=1e-5):
        raise ValueError(f"PCA disagrees with the recorded projection (max error {deviation:.3g}).")
    print(f"{len(frames)} frames, {header['dims']} dimensions, PCA max error {deviation:.3g}")
    return ref


def plot(header, frames, xyz, output):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    p = header["prompt_tokens"]
    fig = plt.figure(figsize=(10, 7), facecolor="#0b1420")
    ax = fig.add_subplot(projection="3d", facecolor="#0b1420")
    for points, color in [(xyz[:p], "#53d7c7"), (xyz[p:], "#ffb76b")]:
        if len(points):
            ax.scatter(*points.T, s=45, color=color, alpha=.85, edgecolors="none")
    show = {p-1, len(frames)-1}
    show.update(i for i, f in enumerate(frames) if f["piece"].strip().lower()=="bank")
    for i in sorted(show):
        ax.text(*xyz[i], f'  {frames[i]["piece"].strip()}  #{i+1}', color="#ecf4fa", fontsize=9)
    for axis, k in zip([ax.xaxis, ax.yaxis, ax.zaxis], range(3)):
        axis.set_pane_color((.04,.08,.12,1))
        axis.label.set_color("#b6c9cf")
        axis.set_label_text(f"PC{k+1}  ({100*header['variance'][k]:.1f}%)")
    ax.tick_params(colors="#9caeb9", labelsize=8)
    fig.suptitle("Embedding Cosmos", fontsize=23, color="#e7f5f6", y=.96)
    fig.text(.5,.88,f'{header["model"]}  /  {len(frames)} positions  /  {header["dims"]} dimensions',
             color="#91aebf", ha="center", fontsize=10)
    handles = [Line2D([],[],marker="o",linestyle="",color=c,label=t)
               for c,t in [("#53d7c7","Prompt"),("#ffb76b","Generated")]]
    ax.legend(handles=handles, loc="upper left", facecolor="#162332", labelcolor="#e7f5f6", framealpha=.9)
    if output:
        fig.savefig(output,dpi=155,bbox_inches="tight",facecolor=fig.get_facecolor())
    else:
        plt.show()


if __name__ == "__main__":
    cmd = argparse.ArgumentParser(description=__doc__)
    cmd.add_argument("trace", type=Path)
    cmd.add_argument("--verify", action="store_true", help="Recompute PCA and check measured attention rows")
    cmd.add_argument("--check-only", action="store_true", help="Validate without drawing")
    cmd.add_argument("--output", type=Path, help="Save a PNG instead of opening a window")
    args = cmd.parse_args()
    meta, tokens = read_trace(args.trace)
    points = verify(meta,tokens) if args.verify or args.check_only else np.array([f["xyz"] for f in tokens])
    if not args.check_only:
        plot(meta,tokens,points,args.output)
