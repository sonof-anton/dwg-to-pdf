"""DWG to PDF - plot every DWG in a folder and merge them into one PDF.

Uses AutoCAD's core console (accoreconsole.exe, ships with AutoCAD / AutoCAD LT)
to plot each drawing's model space through "DWG To PDF.pc3", then merges the
pages with pypdf, one bookmark per drawing.

Run with no arguments for the window, or:
    python dwg_to_pdf.py <folder> [--color] [--paper NAME] [--out FILE] [--recurse]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
LISP_FILE = APP_DIR / "d2p.lsp"
PLOT_TIMEOUT_S = 120

PAPER_CHOICES = [
    "AUTO",
    "ANSI full bleed A (11.00 x 8.50 Inches)",
    "ANSI full bleed B (17.00 x 11.00 Inches)",
    "ANSI full bleed C (22.00 x 17.00 Inches)",
    "ARCH full bleed C (24.00 x 18.00 Inches)",
    "ANSI full bleed D (34.00 x 22.00 Inches)",
    "ARCH full bleed D (36.00 x 24.00 Inches)",
    "ANSI full bleed E (44.00 x 34.00 Inches)",
    "ARCH full bleed E (48.00 x 36.00 Inches)",
]


# ---------------------------------------------------------------- core

def find_core_console():
    """Newest AutoCAD (full or LT) core console; DWG TrueView's has no LISP."""
    found = []
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),):
        autodesk = Path(root) / "Autodesk"
        if autodesk.is_dir():
            for exe in autodesk.glob("*/accoreconsole.exe"):
                if "TrueView" not in exe.parent.name:
                    found.append(exe)
    if not found:
        return None
    nums = lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)] or [0]
    return max(found, key=nums)


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def list_dwgs(folder, recurse=False):
    pattern = "**/*" if recurse else "*"
    return sorted((p for p in Path(folder).glob(pattern)
                   if p.is_file() and p.suffix.lower() == ".dwg"), key=natural_key)


def lisp_source():
    """d2p.lsp pasted into the script instead of (load)-ed: AutoCAD's SECURELOAD
    cancels loading LISP files from folders that aren't in its trusted list.
    Comments and blank lines are stripped - a blank line in a script is Enter.
    (So d2p.lsp must not use ';' inside a string.)"""
    lines = []
    for line in LISP_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split(";", 1)[0]
        if line.strip():
            lines.append(line.rstrip())
    return "\n".join(lines)


def plot_one(console, dwg, pdf, work, ctb, paper, log):
    """Plot one drawing to `pdf`. Works on a copy so the original is never touched."""
    copy = work / ("in_" + dwg.name)
    shutil.copy2(dwg, copy)
    script = work / "plot.scr"
    fwd = lambda p: str(p).replace("\\", "/")
    script.write_text(
        "FILEDIA 0\n"
        "BACKGROUNDPLOT 0\n"
        f"{lisp_source()}\n"
        f'(d2p-plot "{fwd(pdf)}" "{ctb}" "{paper}")\n'
        "_.QUIT\n_Y\n",
        encoding="ascii")
    if pdf.exists():
        pdf.unlink()
    proc = subprocess.Popen(
        [str(console), "/i", str(copy), "/s", str(script), "/l", "en-US"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        out, _ = proc.communicate(timeout=PLOT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        log(f"   (AutoCAD didn't close by itself after {PLOT_TIMEOUT_S}s - closed it)")
    text = out.decode("utf-16-le", errors="ignore") if b"\x00" in out else out.decode(errors="ignore")
    m = re.search(r"D2P-PAPER=([A-Z][^\r\n\"]+)", text)  # skip the echoed source line
    copy.unlink(missing_ok=True)
    if not pdf.exists() or pdf.stat().st_size == 0:
        tail = "\n".join(l for l in text.splitlines() if l.strip())[-800:]
        raise RuntimeError(f"no PDF produced. AutoCAD said:\n{tail}")
    return m.group(1).strip() if m else "?"


def merge(pdfs, names, out_file):
    from pypdf import PdfReader, PdfWriter
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # AutoCAD PDFs trip harmless warnings
    w = PdfWriter()
    for pdf, name in zip(pdfs, names):
        w.append(str(pdf), outline_item=name, import_outline=False)
    tmp = out_file.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        w.write(f)
    os.replace(tmp, out_file)
    return len(PdfReader(str(out_file)).pages)


def convert(folder, out_file, color=False, paper="AUTO", recurse=False, log=print, cancel=None):
    console = find_core_console()
    if not console:
        raise RuntimeError("AutoCAD / AutoCAD LT not found (need accoreconsole.exe under Program Files\\Autodesk).")
    if not LISP_FILE.exists():
        raise RuntimeError(f"Missing {LISP_FILE}")
    dwgs = list_dwgs(folder, recurse)
    if not dwgs:
        raise RuntimeError("No .dwg files in that folder.")
    log(f"Using {console.parent.name}")
    log(f"{len(dwgs)} drawing(s) found.\n")
    ctb = "" if color else "monochrome.ctb"
    work = Path(tempfile.mkdtemp(prefix="dwg2pdf_"))
    pdfs, names, failed = [], [], []
    try:
        for i, dwg in enumerate(dwgs, 1):
            if cancel and cancel.is_set():
                raise RuntimeError("Cancelled.")
            pdf = work / f"{i:04d}.pdf"
            label = str(dwg.relative_to(folder).with_suffix(""))
            t = time.time()
            log(f"[{i}/{len(dwgs)}] {label} ...")
            try:
                used = plot_one(console, dwg, pdf, work, ctb, paper, log)
                log(f"   ok - {used} ({time.time() - t:.0f}s)")
                pdfs.append(pdf)
                names.append(label)
            except Exception as e:
                log(f"   FAILED: {e}")
                failed.append(label)
        if not pdfs:
            raise RuntimeError("Nothing plotted.")
        log("\nMerging ...")
        pages = merge(pdfs, names, Path(out_file))
        log(f"Done: {pages} page(s) -> {out_file}")
        if failed:
            log(f"\nWARNING - left out (failed): {', '.join(failed)}")
        return pages, failed
    finally:
        shutil.rmtree(work, ignore_errors=True)


def default_output(folder):
    folder = Path(folder)
    return folder / f"{folder.name} - All Drawings.pdf"


# ---------------------------------------------------------------- window

def run_gui(initial_folder=None):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("DWG to PDF")
    root.geometry("760x520")
    root.minsize(600, 400)

    folder_var = tk.StringVar(value=initial_folder or "")
    out_var = tk.StringVar()
    color_var = tk.BooleanVar(value=False)
    recurse_var = tk.BooleanVar(value=False)
    paper_var = tk.StringVar(value="AUTO")
    status_var = tk.StringVar(value="Pick a folder of DWGs.")
    cancel = threading.Event()
    state = {"busy": False, "last": None}

    def refresh(*_):
        f = folder_var.get().strip()
        if f and Path(f).is_dir():
            out_var.set(str(default_output(f)))
            n = len(list_dwgs(f, recurse_var.get()))
            status_var.set(f"{n} DWG file(s) in folder.")
        else:
            status_var.set("Pick a folder of DWGs.")

    def pick_folder():
        f = filedialog.askdirectory(initialdir=folder_var.get() or None, title="Folder with DWG files")
        if f:
            folder_var.set(os.path.normpath(f))
            refresh()

    def pick_out():
        f = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                         initialfile=Path(out_var.get()).name if out_var.get() else "",
                                         initialdir=folder_var.get() or None)
        if f:
            out_var.set(os.path.normpath(f))

    def log(msg):
        root.after(0, lambda: (logbox.insert("end", msg + "\n"), logbox.see("end")))

    def finish(ok, msg):
        state["busy"] = False
        go_btn.config(state="normal")
        cancel_btn.config(state="disabled")
        status_var.set(msg)
        if ok:
            open_btn.config(state="normal")

    def start():
        f, out = folder_var.get().strip(), out_var.get().strip()
        if not f or not Path(f).is_dir():
            messagebox.showerror("DWG to PDF", "Pick a folder first.")
            return
        if Path(out).exists() and not messagebox.askyesno("DWG to PDF", f"{Path(out).name} already exists.\nReplace it?"):
            return
        logbox.delete("1.0", "end")
        cancel.clear()
        state["busy"] = True
        go_btn.config(state="disabled")
        cancel_btn.config(state="normal")
        open_btn.config(state="disabled")
        status_var.set("Working ...")

        def work():
            try:
                pages, failed = convert(Path(f), Path(out), color_var.get(), paper_var.get(),
                                        recurse_var.get(), log, cancel)
                state["last"] = out
                msg = f"Done - {pages} page(s)." + (f" {len(failed)} failed, see log." if failed else "")
                root.after(0, finish, True, msg)
            except Exception as e:
                log(f"\nERROR: {e}")
                root.after(0, finish, False, f"Error: {e}".splitlines()[0])

        threading.Thread(target=work, daemon=True).start()

    def open_pdf():
        if state["last"] and Path(state["last"]).exists():
            os.startfile(state["last"])

    pad = {"padx": 8, "pady": 4}
    frm = ttk.Frame(root)
    frm.pack(fill="x", **pad)
    frm.columnconfigure(1, weight=1)
    ttk.Label(frm, text="DWG folder:").grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=folder_var).grid(row=0, column=1, sticky="ew", padx=4)
    ttk.Button(frm, text="Browse...", command=pick_folder).grid(row=0, column=2)
    ttk.Label(frm, text="Save PDF as:").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(frm, textvariable=out_var).grid(row=1, column=1, sticky="ew", padx=4)
    ttk.Button(frm, text="Change...", command=pick_out).grid(row=1, column=2)

    opts = ttk.Frame(root)
    opts.pack(fill="x", **pad)
    ttk.Label(opts, text="Sheet size:").pack(side="left")
    ttk.Combobox(opts, textvariable=paper_var, values=PAPER_CHOICES, state="readonly", width=40).pack(side="left", padx=4)
    ttk.Checkbutton(opts, text="Color", variable=color_var).pack(side="left", padx=8)
    ttk.Checkbutton(opts, text="Include subfolders", variable=recurse_var, command=refresh).pack(side="left")

    btns = ttk.Frame(root)
    btns.pack(fill="x", **pad)
    go_btn = ttk.Button(btns, text="Make PDF", command=start)
    go_btn.pack(side="left")
    cancel_btn = ttk.Button(btns, text="Cancel", command=cancel.set, state="disabled")
    cancel_btn.pack(side="left", padx=4)
    open_btn = ttk.Button(btns, text="Open PDF", command=open_pdf, state="disabled")
    open_btn.pack(side="left")
    ttk.Label(btns, textvariable=status_var).pack(side="left", padx=12)

    logbox = ScrolledText(root, height=15, font=("Consolas", 9))
    logbox.pack(fill="both", expand=True, **pad)

    folder_var.trace_add("write", lambda *_: refresh())
    refresh()

    def on_close():
        if state["busy"] and not messagebox.askyesno("DWG to PDF", "Still working. Quit anyway?"):
            return
        cancel.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ---------------------------------------------------------------- entry

def main():
    ap = argparse.ArgumentParser(description="Plot every DWG in a folder into one PDF.")
    ap.add_argument("folder", nargs="?", help="folder of DWGs (opens the window if --run not given)")
    ap.add_argument("--run", action="store_true", help="convert without opening the window")
    ap.add_argument("--out", help="output PDF (default: '<folder> - All Drawings.pdf' in the folder)")
    ap.add_argument("--color", action="store_true", help="plot in color instead of black and white")
    ap.add_argument("--paper", default="AUTO", help="DWG To PDF paper name, or AUTO (default)")
    ap.add_argument("--recurse", action="store_true", help="include subfolders")
    a = ap.parse_args()
    if a.run:
        if not a.folder:
            ap.error("--run needs a folder")
        folder = Path(a.folder)
        convert(folder, Path(a.out) if a.out else default_output(folder), a.color, a.paper, a.recurse)
    else:
        run_gui(a.folder)


if __name__ == "__main__":
    main()
