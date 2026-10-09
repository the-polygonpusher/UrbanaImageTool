"""
Urbana Image Compressor + Renamer
-----------------------------------------------
1. Pick images.
2. Set the batch-level naming fields (Product Group / Range / SKU / Details).
3. Each image's Render View is auto-detected from a number in its original
   filename (1-16), with a manual override available.
4. Compress + rename all images in one pass to:
     Urbana-[Group]-[Range]-[SKU]-[Details]-[RenderView]-[yyyy-mm-dd].ext
5. Clear and start a new batch once export is done.

Run:
    pip install Pillow
    python image_compressor.py
"""

import os
import re
import threading
from datetime import date
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from PIL import Image

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
COMPANY_PREFIX = "Urbana"

# ---------------------------------------------------------------------------
# Decision tree data
# ---------------------------------------------------------------------------

PRODUCT_GROUPS = ["Shelters", "Toilets", "Bridges", "Access", "Screens", "Handrails"]

# name -> SKU code. Only groups with a defined list are included here;
# other groups fall back to free-text entry in the GUI.
PRODUCT_RANGES = {
    "Shelters": {
        "Jarrah": "U100",
        "Banksia": "U200",
        "Acacia": "U300",
        "Ironbark": "U400",
        "Black Bean": "U500",
        "Casuarina": "U600",
        "Grevillea": "U700",
        "Melaleuca": "U800",
        "Bunya": "U900",
    },
    "Toilets": {
        "Pambula": "UPI-1100",
        "Echuca": "UPI-1200",
        "Karinya": "UPI-1300",
        "Narooma": "UPI-1400",
        "Taronga": "UPI-1500",
        "Wollombi": "UPI-1600",
    },
}

PRODUCT_DETAILS = {
    "Shelters": [
        "timber-skillion",
        "steel-shs-skillion",
        "steel-post-timber",
        "steel-UA-skillion",
        "hardwood-post",
        "steel-UB",
    ],
    "Toilets": [
        "timber",
        "steel-shs",
        "steel-post-timber",
    ],
}

RENDER_VIEWS = {
    1: "front-right-side-angle-view",
    2: "front-right-angle-view",
    3: "front-view",
    4: "front-left-angle-view",
    5: "front-left-side-angle-view",
    6: "left-side-angle-view",
    7: "left-side-view",
    8: "left-rear-side-angle-view",
    9: "rear-left-side-angle-view",
    10: "rear-left-angle-view",
    11: "rear-view",
    12: "rear-right-angle-view",
    13: "rear-right-side-angle-view",
    14: "right-rear-side-angle-view",
    15: "right-side-view",
    16: "right-side-angle-view",
}


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize(text: str) -> str:
    """Strip characters that are invalid in filenames on Windows/Mac/Linux."""
    return _INVALID_FILENAME_CHARS.sub("", text).strip()


def extract_view_number(filename: str):
    """
    Look for a 1-16 camera-view number in a filename, e.g. 'shelter_03.jpg' -> 3.
    Takes the LAST number found in the filename stem. Returns None if no
    number in range 1-16 is found.
    """
    stem = os.path.splitext(filename)[0]
    matches = re.findall(r"\d+", stem)
    if not matches:
        return None
    num = int(matches[-1])
    return num if 1 <= num <= 16 else None


def build_filename(group: str, range_name: str, sku: str, details: str,
                    view_name: str, date_str: str, ext: str) -> str:
    parts = [COMPANY_PREFIX, group, range_name, sku, details, view_name, date_str]
    clean_parts = [sanitize(p) for p in parts if sanitize(p)]
    return "-".join(clean_parts) + ext.lower()


def unique_path(folder: str, filename: str) -> str:
    """Avoid overwriting an existing file by appending -2, -3, etc."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(folder, filename)
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{base}-{counter}{ext}")
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# Core compression logic
# ---------------------------------------------------------------------------

def compress_image(src_path: str, out_path: str, quality: int):
    """Compress a single image to an explicit out_path. Returns (before, after) sizes."""
    original_size = os.path.getsize(src_path)
    ext = os.path.splitext(out_path)[1].lower()

    with Image.open(src_path) as img:
        img_format = img.format or ext.replace(".", "").upper()

        if img.mode in ("RGBA", "P") and img_format == "JPEG":
            img = img.convert("RGB")

        save_kwargs = {}
        if img_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif img_format == "PNG":
            save_kwargs["optimize"] = True
            save_kwargs["compress_level"] = max(0, min(9, 9 - round(quality / 11)))

        img.save(out_path, **save_kwargs)

    new_size = os.path.getsize(out_path)
    return original_size, new_size


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class ImageCompressorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Urbana Image Tool")
        self.geometry("760x560")
        self.minsize(680, 480)

        # file_path -> {"view_number": int|None, "view_name": str|None}
        self.files = {}
        self.output_folder = ""

        self._build_widgets()

    # -- Layout --------------------------------------------------------

    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        # --- Naming fields ---
        naming_frame = ttk.LabelFrame(self, text="Batch naming (applies to every image in this batch)")
        naming_frame.pack(fill="x", **pad)

        # Row 1: Group / Range
        row1 = ttk.Frame(naming_frame)
        row1.pack(fill="x", padx=8, pady=4)

        ttk.Label(row1, text="Product Group:").pack(side="left")
        self.group_var = tk.StringVar()
        self.group_combo = ttk.Combobox(
            row1, textvariable=self.group_var, values=PRODUCT_GROUPS, state="readonly", width=14
        )
        self.group_combo.pack(side="left", padx=(4, 16))
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_changed)

        ttk.Label(row1, text="Product Range:").pack(side="left")
        self.range_var = tk.StringVar()
        self.range_combo = ttk.Combobox(row1, textvariable=self.range_var, width=16)
        self.range_combo.pack(side="left", padx=(4, 16))
        self.range_combo.bind("<<ComboboxSelected>>", self._on_range_changed)

        ttk.Label(row1, text="SKU:").pack(side="left")
        self.sku_var = tk.StringVar()
        self.sku_entry = ttk.Entry(row1, textvariable=self.sku_var, width=12)
        self.sku_entry.pack(side="left", padx=(4, 0))

        # Row 2: Details
        row2 = ttk.Frame(naming_frame)
        row2.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Label(row2, text="Product Details:").pack(side="left")
        self.details_var = tk.StringVar()
        self.details_combo = ttk.Combobox(row2, textvariable=self.details_var, width=24)
        self.details_combo.pack(side="left", padx=(4, 16))

        ttk.Label(row2, text="Date:").pack(side="left")
        self.date_str = date.today().strftime("%Y-%m-%d")
        self.date_label = ttk.Label(row2, text=self.date_str, foreground="gray")
        self.date_label.pack(side="left", padx=(4, 0))

        # --- File controls ---
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", **pad)

        ttk.Button(top_frame, text="Add Images...", command=self.add_files).pack(side="left")
        ttk.Button(top_frame, text="Clear List", command=self.clear_files).pack(side="left", padx=(8, 0))
        ttk.Button(top_frame, text="Edit View for Selected...", command=self.edit_selected_view).pack(
            side="left", padx=(8, 0)
        )

        # --- File list ---
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, **pad)

        columns = ("file", "view_number", "view_name", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("file", text="File")
        self.tree.heading("view_number", text="View #")
        self.tree.heading("view_name", text="Render View")
        self.tree.heading("status", text="Status")
        self.tree.column("file", width=220)
        self.tree.column("view_number", width=70, anchor="center")
        self.tree.column("view_name", width=220)
        self.tree.column("status", width=140)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=scrollbar.set)

        # --- Output folder ---
        out_frame = ttk.Frame(self)
        out_frame.pack(fill="x", **pad)

        ttk.Button(out_frame, text="Choose Output Folder...", command=self.choose_output).pack(side="left")
        self.output_label = ttk.Label(out_frame, text="No folder selected", foreground="gray")
        self.output_label.pack(side="left", padx=(8, 0))

        # --- Quality slider ---
        quality_frame = ttk.Frame(self)
        quality_frame.pack(fill="x", **pad)

        ttk.Label(quality_frame, text="Quality:").pack(side="left")
        self.quality_var = tk.IntVar(value=90)
        self.quality_slider = ttk.Scale(
            quality_frame, from_=10, to=95, orient="horizontal",
            variable=self.quality_var, command=self._update_quality_label
        )
        self.quality_slider.pack(side="left", fill="x", expand=True, padx=8)
        self.quality_value_label = ttk.Label(quality_frame, text="90")
        self.quality_value_label.pack(side="left")

        # --- Action buttons + progress ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)

        self.compress_button = ttk.Button(
            action_frame, text="Compress & Rename", command=self.start_processing
        )
        self.compress_button.pack(side="left")

        self.new_batch_button = ttk.Button(action_frame, text="New Batch", command=self.new_batch)
        self.new_batch_button.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(action_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # --- Status ---
        self.status_label = ttk.Label(self, text="Add images to get started.", foreground="gray")
        self.status_label.pack(fill="x", **pad)

    def _update_quality_label(self, _event=None):
        self.quality_value_label.config(text=str(int(self.quality_var.get())))

    # -- Naming field cascading -----------------------------------------

    def _on_group_changed(self, _event=None):
        group = self.group_var.get()
        ranges = PRODUCT_RANGES.get(group)
        details = PRODUCT_DETAILS.get(group)

        if ranges:
            self.range_combo.config(values=list(ranges.keys()), state="readonly")
        else:
            self.range_combo.config(values=[], state="normal")
        self.range_var.set("")
        self.sku_var.set("")

        if details:
            self.details_combo.config(values=details, state="readonly")
        else:
            self.details_combo.config(values=[], state="normal")
        self.details_var.set("")

    def _on_range_changed(self, _event=None):
        group = self.group_var.get()
        ranges = PRODUCT_RANGES.get(group, {})
        chosen = self.range_var.get()
        if chosen in ranges:
            self.sku_var.set(ranges[chosen])

    # -- File handling ---------------------------------------------------

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Images", " ".join(f"*{e}" for e in SUPPORTED_EXTS))],
        )
        for p in paths:
            if p in self.files:
                continue
            view_number = extract_view_number(os.path.basename(p))
            view_name = RENDER_VIEWS.get(view_number)
            self.files[p] = {"view_number": view_number, "view_name": view_name}
            self.tree.insert(
                "", "end", iid=p,
                values=(
                    os.path.basename(p),
                    view_number if view_number else "?",
                    view_name if view_name else "(not detected - set manually)",
                    "Ready",
                ),
            )
        self._update_status()

    def clear_files(self):
        self.files.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._update_status()

    def edit_selected_view(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select one or more files in the list first.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Set Render View")
        dialog.geometry("340x110")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Render View for selected file(s):").pack(pady=(10, 4))
        view_var = tk.StringVar()
        names = [f"{num}: {name}" for num, name in RENDER_VIEWS.items()]
        combo = ttk.Combobox(dialog, textvariable=view_var, values=names, state="readonly", width=38)
        combo.pack(pady=4)

        def apply_choice():
            choice = view_var.get()
            if not choice:
                dialog.destroy()
                return
            num_str, name = choice.split(": ", 1)
            num = int(num_str)
            for path in selected:
                self.files[path]["view_number"] = num
                self.files[path]["view_name"] = name
                self.tree.item(path, values=(os.path.basename(path), num, name, "Ready"))
            dialog.destroy()

        ttk.Button(dialog, text="Apply", command=apply_choice).pack(pady=6)

    def choose_output(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_folder = folder
            self.output_label.config(text=folder, foreground="black")

    def _update_status(self, text=None):
        if text:
            self.status_label.config(text=text)
        else:
            self.status_label.config(text=f"{len(self.files)} file(s) selected.")

    # -- Validation --------------------------------------------------------

    def _validate_before_processing(self) -> bool:
        if not self.files:
            messagebox.showwarning("No files", "Add at least one image first.")
            return False
        if not self.output_folder:
            messagebox.showwarning("No output folder", "Choose an output folder first.")
            return False
        if not self.group_var.get():
            messagebox.showwarning("Missing field", "Choose a Product Group.")
            return False

        missing_views = [os.path.basename(p) for p, info in self.files.items() if not info["view_name"]]
        if missing_views:
            proceed = messagebox.askyesno(
                "Some views not detected",
                "These files have no detected Render View:\n\n"
                + "\n".join(missing_views)
                + "\n\nUse 'Edit View for Selected...' to set them manually, "
                  "or continue and they'll be labeled 'unknown-view'.\n\nContinue anyway?",
            )
            if not proceed:
                return False
        return True

    # -- Compression + renaming --------------------------------------------

    def start_processing(self):
        if not self._validate_before_processing():
            return

        self.compress_button.config(state="disabled")
        self.progress.config(maximum=len(self.files), value=0)

        thread = threading.Thread(target=self._process_all, daemon=True)
        thread.start()

    def _process_all(self):
        group = self.group_var.get()
        range_name = self.range_var.get()
        sku = self.sku_var.get()
        details = self.details_var.get()
        quality = int(self.quality_var.get())

        total_before = 0
        total_after = 0
        errors = []

        for i, (path, info) in enumerate(self.files.items(), start=1):
            try:
                ext = os.path.splitext(path)[1]
                view_name = info["view_name"] or "unknown-view"
                filename = build_filename(group, range_name, sku, details, view_name, self.date_str, ext)
                out_path = unique_path(self.output_folder, filename)

                before, after = compress_image(path, out_path, quality)
                total_before += before
                total_after += after
                self.after(0, self._set_row_status, path, "Done")
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
                self.after(0, self._set_row_status, path, "Error")

            self.after(0, self._set_progress, i)

        self.after(0, self._processing_done, total_before, total_after, errors)

    def _set_row_status(self, path, status):
        values = list(self.tree.item(path, "values"))
        values[3] = status
        self.tree.item(path, values=values)

    def _set_progress(self, value):
        self.progress.config(value=value)

    def _processing_done(self, total_before, total_after, errors):
        self.compress_button.config(state="normal")

        if errors:
            messagebox.showerror("Some files failed", "\n".join(errors))

        if total_before > 0:
            saved_pct = (1 - total_after / total_before) * 100
            self._update_status(
                f"Done. {human_size(total_before)} -> {human_size(total_after)} "
                f"({saved_pct:.1f}% smaller). Saved to: {self.output_folder}"
            )
        else:
            self._update_status("Nothing processed.")

    # -- New batch -----------------------------------------------------

    def new_batch(self):
        self.clear_files()
        self.group_var.set("")
        self.range_var.set("")
        self.sku_var.set("")
        self.details_var.set("")
        self.range_combo.config(values=[], state="readonly")
        self.details_combo.config(values=[], state="readonly")
        self.date_str = date.today().strftime("%Y-%m-%d")
        self.date_label.config(text=self.date_str)
        self.progress.config(value=0)
        self._update_status("New batch started. Add images to continue.")


if __name__ == "__main__":
    app = ImageCompressorApp()
    app.mainloop()