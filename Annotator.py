import os
import json
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw


class Annotator:
    def __init__(self, root):
        self.root = root
        self.root.title("Polygon Annotator")
        self.root.geometry("1200x780")

        # State variables
        self.image_folder = ""
        self.image_files = []
        self.current_image_index = 0
        self.current_image = None
        self.photo_tk = None

        # Drawing state: polygons are stored in display/canvas coordinates
        self.polygons = []
        self.current_polygon = []

        # Display dimensions and image placement
        self.disp_w = 0
        self.disp_h = 0
        self.image_x = 0
        self.image_y = 0
        self.scale_x = 1.0
        self.scale_y = 1.0

        self.export_format = tk.StringVar(value="YOLO Segmentation TXT")
        self.setup_ui()

    # ------------------------------------------------------------------ #
    # Theme / UI
    # ------------------------------------------------------------------ #
    PALETTE = {
        "bg": "#0f1115",
        "panel": "#161a22",
        "card": "#1d222c",
        "card_hover": "#262c38",
        "border": "#2b3140",
        "text": "#e7e9ef",
        "muted": "#8b93a7",
        "accent": "#6366f1",
        "accent_hover": "#7b7ef4",
        "success": "#16a34a",
        "success_hover": "#22c55e",
        "danger": "#b4414b",
        "danger_hover": "#d4505c",
        "canvas": "#0b0d11",
        "poly": "#2dd4bf",
        "vertex": "#ffffff",
        "active": "#fbbf24",
    }

    def _pick_font(self):
        import tkinter.font as tkfont
        available = set(tkfont.families())
        for name in ("Segoe UI Variable", "Segoe UI", "SF Pro Text",
                     "Helvetica Neue", "Inter", "Roboto", "Ubuntu", "DejaVu Sans"):
            if name in available:
                return name
        return "Arial"

    def apply_theme(self):
        p = self.PALETTE
        self.font_family = self._pick_font()
        ff = self.font_family
        self.root.configure(bg=p["bg"])
        self.root.minsize(900, 600)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=p["panel"], foreground=p["text"],
                        font=(ff, 10), borderwidth=0, focuscolor=p["panel"])
        style.configure("Panel.TFrame", background=p["panel"])
        style.configure("Card.TFrame", background=p["card"])
        style.configure("TLabel", background=p["panel"], foreground=p["text"])
        style.configure("Title.TLabel", background=p["panel"],
                        foreground=p["text"], font=(ff, 15, "bold"))
        style.configure("Subtitle.TLabel", background=p["panel"],
                        foreground=p["muted"], font=(ff, 9))
        style.configure("Section.TLabel", background=p["panel"],
                        foreground=p["muted"], font=(ff, 8, "bold"))
        style.configure("Hint.TLabel", background=p["card"],
                        foreground=p["muted"], font=(ff, 9))
        style.configure("Status.TLabel", background=p["bg"],
                        foreground=p["muted"], font=(ff, 9))

        def button(name, bg, hover, fg="#ffffff", bold=False):
            style.configure(name, background=bg, foreground=fg, padding=(12, 8),
                            font=(ff, 10, "bold" if bold else "normal"),
                            relief="flat", borderwidth=0)
            style.map(name,
                      background=[("pressed", hover), ("active", hover)],
                      foreground=[("active", fg)])

        button("Primary.TButton", p["accent"], p["accent_hover"], bold=True)
        button("Success.TButton", p["success"], p["success_hover"], bold=True)
        button("Secondary.TButton", p["card"], p["card_hover"], fg=p["text"])
        button("Danger.TButton", p["card"], p["danger"], fg=p["text"])

        style.configure("TCombobox", fieldbackground=p["card"],
                        background=p["card"], foreground=p["text"],
                        arrowcolor=p["muted"], bordercolor=p["border"],
                        lightcolor=p["card"], darkcolor=p["card"],
                        selectbackground=p["card"], selectforeground=p["text"],
                        padding=6)
        style.map("TCombobox",
                  fieldbackground=[("readonly", p["card"])],
                  foreground=[("readonly", p["text"])],
                  selectbackground=[("readonly", p["card"])],
                  selectforeground=[("readonly", p["text"])],
                  bordercolor=[("focus", p["accent"])])
        self.root.option_add("*TCombobox*Listbox.background", p["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", (ff, 10))

        style.configure("Vertical.TScrollbar", background=p["card_hover"],
                        troughcolor=p["panel"], bordercolor=p["panel"],
                        arrowcolor=p["muted"], lightcolor=p["card_hover"],
                        darkcolor=p["card_hover"], gripcount=0)
        style.map("Vertical.TScrollbar",
                  background=[("active", p["accent"])])

    def _section_label(self, parent, text):
        ttk.Label(parent, text=text.upper(), style="Section.TLabel").pack(
            fill=tk.X, pady=(14, 6)
        )

    def setup_ui(self):
        p = self.PALETTE
        self.apply_theme()
        ff = self.font_family

        # Status bar (bottom)
        status_bar = tk.Frame(self.root, bg=p["bg"])
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Select an image folder to begin")
        ttk.Label(status_bar, textvariable=self.status_var,
                  style="Status.TLabel").pack(side=tk.LEFT, padx=14, pady=6)
        self.coords_var = tk.StringVar(value="")
        ttk.Label(status_bar, textvariable=self.coords_var,
                  style="Status.TLabel").pack(side=tk.RIGHT, padx=14, pady=6)

        # Left Panel: Controls & List
        left_frame = ttk.Frame(self.root, style="Panel.TFrame", width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)
        inner = ttk.Frame(left_frame, style="Panel.TFrame")
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        ttk.Label(inner, text="Polygon Annotator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(inner, text="Segmentation labeling & export",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Button(inner, text="Select Image Folder", style="Primary.TButton",
                   command=self.load_folder, cursor="hand2").pack(fill=tk.X)

        # Image list
        self._section_label(inner, "Images")
        list_wrap = tk.Frame(inner, bg=p["border"], padx=1, pady=1)
        list_wrap.pack(fill=tk.BOTH, expand=True)
        list_inner = tk.Frame(list_wrap, bg=p["card"])
        list_inner.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_inner, orient=tk.VERTICAL,
                               style="Vertical.TScrollbar")
        self.listbox = tk.Listbox(
            list_inner, height=10, bg=p["card"], fg=p["text"],
            selectbackground=p["accent"], selectforeground="#ffffff",
            activestyle="none", relief="flat", highlightthickness=0,
            borderwidth=0, font=(ff, 10), exportselection=False,
            yscrollcommand=scroll.set
        )
        scroll.config(command=self.listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        # Navigation and Actions
        nav_frame = ttk.Frame(inner, style="Panel.TFrame")
        nav_frame.pack(fill=tk.X, pady=(10, 0))
        nav_frame.columnconfigure((0, 1), weight=1, uniform="nav")
        ttk.Button(nav_frame, text="◀  Prev", style="Secondary.TButton",
                   command=self.prev_image, cursor="hand2").grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(nav_frame, text="Next  ▶", style="Secondary.TButton",
                   command=self.next_image, cursor="hand2").grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        self._section_label(inner, "Edit")
        clear_frame = ttk.Frame(inner, style="Panel.TFrame")
        clear_frame.pack(fill=tk.X)
        clear_frame.columnconfigure((0, 1), weight=1, uniform="clr")
        ttk.Button(clear_frame, text="Clear Current", style="Danger.TButton",
                   command=self.clear_current_polygon, cursor="hand2").grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(clear_frame, text="Clear All", style="Danger.TButton",
                   command=self.clear_all_polygons, cursor="hand2").grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        # Keep the original TXT save button/function
        ttk.Button(
            inner, text="Save Annotations (TXT)", style="Success.TButton",
            command=self.save_annotations, cursor="hand2"
        ).pack(fill=tk.X, pady=(10, 0))

        # Added export options
        self._section_label(inner, "Additional export format")
        formats = [
            "YOLO Segmentation TXT",
            "Binary PNG Masks",
            "Grayscale PNG Masks",
            "COCO Segmentation JSON",
            "LabelMe JSON",
            "Polygon Coordinates JSON",
            "Pascal VOC XML (Bounding Boxes)"
        ]
        self.format_combo = ttk.Combobox(
            inner, textvariable=self.export_format,
            values=formats, state="readonly"
        )
        self.format_combo.pack(fill=tk.X)

        exp_frame = ttk.Frame(inner, style="Panel.TFrame")
        exp_frame.pack(fill=tk.X, pady=(8, 0))
        exp_frame.columnconfigure((0, 1), weight=1, uniform="exp")
        ttk.Button(
            exp_frame, text="Export Current", style="Secondary.TButton",
            command=self.export_current_image, cursor="hand2"
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            exp_frame, text="Batch Export", style="Primary.TButton",
            command=self.batch_export, cursor="hand2"
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Instructions card
        hint_card = ttk.Frame(inner, style="Card.TFrame")
        hint_card.pack(fill=tk.X, pady=(14, 0))
        instructions = (
            "Left click   Add polygon point\n"
            "Right click  Close polygon\n"
            "Ctrl+S  Save    ← →  Navigate\n"
            "Esc  Clear current polygon\n\n"
            "Class ID is locked to 0. Batch export uses saved TXT files "
            "plus the current unsaved annotation."
        )
        ttk.Label(hint_card, text=instructions, justify=tk.LEFT,
                  style="Hint.TLabel", wraplength=240).pack(
            fill=tk.X, padx=12, pady=10)

        # Right Panel: Canvas
        self.canvas_frame = tk.Frame(self.root, bg=p["bg"])
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                               padx=(0, 12), pady=12)
        canvas_border = tk.Frame(self.canvas_frame, bg=p["border"], padx=1, pady=1)
        canvas_border.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_border, bg=p["canvas"], cursor="crosshair",
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # Keyboard shortcuts (additive)
        self.root.bind("<Control-s>", lambda e: self.save_annotations())
        self.root.bind("<Escape>", lambda e: self.clear_current_polygon())
        self.root.bind("<Left>", self._on_key_prev)
        self.root.bind("<Right>", self._on_key_next)

    def _on_key_prev(self, event):
        if isinstance(event.widget, ttk.Combobox):
            return
        self.prev_image()

    def _on_key_next(self, event):
        if isinstance(event.widget, ttk.Combobox):
            return
        self.next_image()

    def _on_mouse_move(self, event):
        if not self.photo_tk:
            self.coords_var.set("")
            return
        x, y = self._canvas_point(event)
        if self.current_image is not None and self.disp_w and self.disp_h:
            iw, ih = self.current_image.size
            self.coords_var.set(
                f"x: {int(x / self.disp_w * iw)}   y: {int(y / self.disp_h * ih)}"
            )

    def _update_status(self):
        if not self.image_files:
            self.status_var.set("Select an image folder to begin")
            return
        name = self.image_files[self.current_image_index]
        self.status_var.set(
            f"{name}   •   {self.current_image_index + 1} / {len(self.image_files)}"
            f"   •   {len(self.polygons)} polygon(s)"
            f"   •   {len(self.current_polygon)} point(s) in progress"
        )

    def load_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        self.image_folder = folder
        valid_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
        self.image_files = sorted(
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(valid_exts)
        )

        self.listbox.delete(0, tk.END)
        for f in self.image_files:
            self.listbox.insert(tk.END, f)

        if not self.image_files:
            messagebox.showwarning("No images", "No supported images were found in this folder.")
            return

        self.current_image_index = 0
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(0)
        self.load_image()

    def load_image(self):
        if not self.image_files:
            return

        filename = self.image_files[self.current_image_index]
        filepath = os.path.join(self.image_folder, filename)

        try:
            self.current_image = Image.open(filepath).convert("RGB")
        except Exception as e:
            messagebox.showerror("Image error", f"Could not open image:\n{filepath}\n\n{e}")
            return

        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 700, 600

        img_w, img_h = self.current_image.size
        scale = min(cw / img_w, ch / img_h)
        self.disp_w = max(1, int(img_w * scale))
        self.disp_h = max(1, int(img_h * scale))
        self.scale_x = self.disp_w / img_w
        self.scale_y = self.disp_h / img_h
        self.image_x = (cw - self.disp_w) // 2
        self.image_y = (ch - self.disp_h) // 2

        resized_img = self.current_image.resize(
            (self.disp_w, self.disp_h), Image.Resampling.LANCZOS
        )
        self.photo_tk = ImageTk.PhotoImage(resized_img)

        self.polygons = []
        self.current_polygon = []
        self.load_existing_annotations(filename)
        self.redraw()

    def on_list_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            new_index = selection[0]
            if new_index != self.current_image_index:
                self.current_image_index = new_index
                self.load_image()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_image_index)
            self.listbox.see(self.current_image_index)
            self.load_image()

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_image_index)
            self.listbox.see(self.current_image_index)
            self.load_image()

    def _canvas_point(self, event):
        # Convert canvas coordinates to coordinates relative to the displayed image.
        x = event.x - self.image_x
        y = event.y - self.image_y
        return (
            max(0, min(x, self.disp_w)),
            max(0, min(y, self.disp_h))
        )

    def on_left_click(self, event):
        if not self.photo_tk:
            return
        x, y = self._canvas_point(event)
        self.current_polygon.append((x, y))
        self.redraw()

    def on_right_click(self, event):
        if len(self.current_polygon) > 2:
            self.polygons.append(self.current_polygon)
            self.current_polygon = []
            self.redraw()
        else:
            messagebox.showwarning("Incomplete", "A polygon requires at least 3 points.")

    def clear_current_polygon(self):
        self.current_polygon = []
        self.redraw()

    def clear_all_polygons(self):
        self.polygons = []
        self.current_polygon = []
        self.redraw()

    def redraw(self):
        p = self.PALETTE
        self.canvas.delete("all")
        if self.photo_tk:
            self.canvas.create_image(
                self.image_x, self.image_y, anchor=tk.NW, image=self.photo_tk
            )
        else:
            self.canvas.update_idletasks()
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            self.canvas.create_text(
                cw // 2, ch // 2, fill=p["muted"], justify=tk.CENTER,
                font=(getattr(self, "font_family", "Arial"), 13),
                text="No image loaded\nClick “Select Image Folder” to begin"
            )

        for poly in self.polygons:
            coords = []
            for x, y in poly:
                coords.extend((x + self.image_x, y + self.image_y))
            self.canvas.create_polygon(coords, outline=p["poly"], fill="", width=2)
            for x, y in poly:
                x += self.image_x
                y += self.image_y
                self.canvas.create_oval(x-3, y-3, x+3, y+3,
                                        fill=p["vertex"], outline=p["poly"], width=1)

        if self.current_polygon:
            for i, (x, y) in enumerate(self.current_polygon):
                x += self.image_x
                y += self.image_y
                if i > 0:
                    px, py = self.current_polygon[i-1]
                    self.canvas.create_line(
                        px + self.image_x, py + self.image_y, x, y,
                        fill=p["active"], width=2
                    )
            for i, (x, y) in enumerate(self.current_polygon):
                x += self.image_x
                y += self.image_y
                r = 5 if i == 0 else 3
                self.canvas.create_oval(x-r, y-r, x+r, y+r,
                                        fill=p["active"], outline="#000000", width=1)

        self._update_status()

    def _txt_path(self, filename):
        return os.path.join(self.image_folder, os.path.splitext(filename)[0] + ".txt")

    def load_existing_annotations(self, filename):
        txt_path = self._txt_path(filename)
        if not os.path.exists(txt_path):
            return

        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 7 and (len(parts) - 1) % 2 == 0:
                        poly = []
                        for i in range(1, len(parts), 2):
                            x = float(parts[i]) * self.disp_w
                            y = float(parts[i + 1]) * self.disp_h
                            poly.append((x, y))
                        self.polygons.append(poly)
        except Exception as e:
            print(f"Failed to load existing annotation: {e}")

    def _polygons_original_pixels(self, polygons=None):
        """Return polygons in original-image pixel coordinates."""
        if self.current_image is None:
            return []
        if polygons is None:
            polygons = self.polygons
        iw, ih = self.current_image.size
        result = []
        for poly in polygons:
            points = []
            for x, y in poly:
                px = max(0.0, min(iw, float(x) / max(self.disp_w, 1) * iw))
                py = max(0.0, min(ih, float(y) / max(self.disp_h, 1) * ih))
                points.append((px, py))
            if len(points) >= 3:
                result.append(points)
        return result

    def _load_polygons_for_file(self, filename):
        """Load YOLO TXT annotations for any image, independent of current canvas."""
        image_path = os.path.join(self.image_folder, filename)
        with Image.open(image_path) as im:
            iw, ih = im.size
        txt_path = self._txt_path(filename)
        polygons = []
        if not os.path.isfile(txt_path):
            # The current image can have annotations not saved to TXT yet.
            if filename == self.image_files[self.current_image_index] and self.current_image is not None:
                return self._polygons_original_pixels()
            return polygons

        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 7 and (len(parts) - 1) % 2 == 0:
                    try:
                        vals = [float(v) for v in parts[1:]]
                        points = [(vals[i] * iw, vals[i + 1] * ih)
                                  for i in range(0, len(vals), 2)]
                        polygons.append(points)
                    except (ValueError, IndexError):
                        continue

        # Current image: include unsaved edits instead of stale TXT.
        if filename == self.image_files[self.current_image_index]:
            return self._polygons_original_pixels()
        return polygons

    def save_annotations(self):
        """Original YOLO segmentation TXT export; kept as a separate action."""
        if not self.image_files:
            return

        filename = self.image_files[self.current_image_index]
        txt_path = self._txt_path(filename)

        if not self.polygons:
            if os.path.exists(txt_path):
                os.remove(txt_path)
            messagebox.showinfo("Saved", "Annotations cleared/saved.")
            return

        iw, ih = self.current_image.size
        with open(txt_path, "w", encoding="utf-8") as f:
            for poly in self._polygons_original_pixels():
                line = ["0"]
                for x, y in poly:
                    line.append(f"{max(0.0, min(1.0, x / iw)):.6f}")
                    line.append(f"{max(0.0, min(1.0, y / ih)):.6f}")
                f.write(" ".join(line) + "\n")

        messagebox.showinfo("Saved", f"Saved annotations to:\n{txt_path}")

    def _output_dir(self, format_name):
        folder_names = {
            "YOLO Segmentation TXT": "export_yolo_txt",
            "Binary PNG Masks": "export_binary_masks",
            "Grayscale PNG Masks": "export_grayscale_masks",
            "COCO Segmentation JSON": "export_coco",
            "LabelMe JSON": "export_labelme",
            "Polygon Coordinates JSON": "export_polygon_json",
            "Pascal VOC XML (Bounding Boxes)": "export_voc_xml",
        }
        path = os.path.join(self.image_folder, folder_names[format_name])
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _make_mask(width, height, polygons, grayscale=False):
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        fill_value = 1 if grayscale else 255
        for poly in polygons:
            if len(poly) >= 3:
                draw.polygon([(round(x), round(y)) for x, y in poly], fill=fill_value)
        return mask

    @staticmethod
    def _bbox_and_area(poly):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x_min, y_min = min(xs), min(ys)
        x_max, y_max = max(xs), max(ys)
        return [x_min, y_min, x_max - x_min, y_max - y_min]

    def _export_one(self, filename, format_name, polygons):
        image_path = os.path.join(self.image_folder, filename)
        with Image.open(image_path) as im:
            width, height = im.size
            image_id_name = os.path.splitext(filename)[0]

        out_dir = self._output_dir(format_name)
        base = os.path.splitext(filename)[0]

        if format_name == "YOLO Segmentation TXT":
            out_path = os.path.join(out_dir, base + ".txt")
            with open(out_path, "w", encoding="utf-8") as f:
                for poly in polygons:
                    if len(poly) < 3:
                        continue
                    vals = ["0"]
                    for x, y in poly:
                        vals.extend((f"{max(0.0, min(1.0, x / width)):.6f}",
                                     f"{max(0.0, min(1.0, y / height)):.6f}"))
                    f.write(" ".join(vals) + "\n")

        elif format_name in ("Binary PNG Masks", "Grayscale PNG Masks"):
            is_gray = format_name == "Grayscale PNG Masks"
            mask = self._make_mask(width, height, polygons, grayscale=is_gray)
            mask.save(os.path.join(out_dir, base + ".png"))

        elif format_name == "Polygon Coordinates JSON":
            data = {
                "image": filename,
                "image_width": width,
                "image_height": height,
                "annotations": [
                    {
                        "class_id": 0,
                        "label": "",
                        "points": [[round(x, 3), round(y, 3)] for x, y in poly]
                    }
                    for poly in polygons if len(poly) >= 3
                ]
            }
            with open(os.path.join(out_dir, base + ".json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        elif format_name == "LabelMe JSON":
            data = {
                "version": "5.5.0",
                "flags": {},
                "shapes": [
                    {
                        "label": "",
                        "points": [[round(x, 3), round(y, 3)] for x, y in poly],
                        "group_id": None,
                        "description": "",
                        "shape_type": "polygon",
                        "flags": {}
                    }
                    for poly in polygons if len(poly) >= 3
                ],
                "imagePath": filename,
                "imageData": None,
                "imageHeight": height,
                "imageWidth": width
            }
            with open(os.path.join(out_dir, base + ".json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        elif format_name == "Pascal VOC XML (Bounding Boxes)":
            root = ET.Element("annotation")
            ET.SubElement(root, "folder").text = os.path.basename(self.image_folder)
            ET.SubElement(root, "filename").text = filename
            size = ET.SubElement(root, "size")
            ET.SubElement(size, "width").text = str(width)
            ET.SubElement(size, "height").text = str(height)
            ET.SubElement(size, "depth").text = "3"
            ET.SubElement(root, "segmented").text = "0"
            for poly in polygons:
                if len(poly) < 3:
                    continue
                x, y, w, h = self._bbox_and_area(poly)
                obj = ET.SubElement(root, "object")
                ET.SubElement(obj, "name").text = ""
                ET.SubElement(obj, "pose").text = "Unspecified"
                ET.SubElement(obj, "truncated").text = "0"
                ET.SubElement(obj, "difficult").text = "0"
                box = ET.SubElement(obj, "bndbox")
                ET.SubElement(box, "xmin").text = str(max(0, int(round(x))))
                ET.SubElement(box, "ymin").text = str(max(0, int(round(y))))
                ET.SubElement(box, "xmax").text = str(min(width, int(round(x + w))))
                ET.SubElement(box, "ymax").text = str(min(height, int(round(y + h))))
            tree = ET.ElementTree(root)
            try:
                ET.indent(tree, space="  ")
            except AttributeError:
                pass
            tree.write(os.path.join(out_dir, base + ".xml"),
                       encoding="utf-8", xml_declaration=True)

    def _export_coco_all(self, files, polygons_by_file):
        out_dir = self._output_dir("COCO Segmentation JSON")
        images = []
        annotations = []
        ann_id = 1
        for image_id, filename in enumerate(files, start=1):
            image_path = os.path.join(self.image_folder, filename)
            with Image.open(image_path) as im:
                width, height = im.size
            images.append({
                "id": image_id, "file_name": filename,
                "width": width, "height": height
            })
            for poly in polygons_by_file.get(filename, []):
                if len(poly) < 3:
                    continue
                flat = []
                for x, y in poly:
                    flat.extend((round(x, 3), round(y, 3)))
                bbox = self._bbox_and_area(poly)
                # Polygon area via shoelace formula
                area = abs(sum(
                    poly[i][0] * poly[(i + 1) % len(poly)][1]
                    - poly[(i + 1) % len(poly)][0] * poly[i][1]
                    for i in range(len(poly))
                )) / 2.0
                annotations.append({
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": 0,
                    "segmentation": [flat],
                    "area": round(area, 3),
                    "bbox": [round(v, 3) for v in bbox],
                    "iscrowd": 0
                })
                ann_id += 1

        data = {
            "info": {"description": " polygon segmentation dataset"},
            "licenses": [],
            "images": images,
            "annotations": annotations,
            "categories": [{"id": 0, "name": "", "supercategory": "road_damage"}]
        }
        with open(os.path.join(out_dir, "annotations_coco.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def export_current_image(self):
        if not self.image_files or self.current_image is None:
            messagebox.showwarning("No image", "Select an image folder first.")
            return
        fmt = self.export_format.get()
        filename = self.image_files[self.current_image_index]
        polygons = self._polygons_original_pixels()
        try:
            if fmt == "COCO Segmentation JSON":
                self._export_coco_all([filename], {filename: polygons})
            else:
                self._export_one(filename, fmt, polygons)
            messagebox.showinfo("Export complete", f"Exported {filename} as {fmt}.\n\nOutput folder:\n{self._output_dir(fmt)}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def batch_export(self):
        if not self.image_files:
            messagebox.showwarning("No images", "Select an image folder first.")
            return
        fmt = self.export_format.get()
        try:
            polygons_by_file = {}
            for filename in self.image_files:
                polygons_by_file[filename] = self._load_polygons_for_file(filename)

            if fmt == "COCO Segmentation JSON":
                self._export_coco_all(self.image_files, polygons_by_file)
            else:
                for filename in self.image_files:
                    self._export_one(filename, fmt, polygons_by_file[filename])

            messagebox.showinfo(
                "Batch export complete",
                f"Exported {len(self.image_files)} images as {fmt}.\n\nOutput folder:\n{self._output_dir(fmt)}"
            )
        except Exception as e:
            messagebox.showerror("Batch export failed", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = Annotator(root)
    root.mainloop()
