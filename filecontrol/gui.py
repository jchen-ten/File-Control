"""Tkinter graphical interface for File Control."""

from __future__ import annotations

import queue
import threading
from tkinter import (
    BooleanVar,
    Button,
    StringVar,
    Tk,
    filedialog,
    messagebox,
)
from tkinter import ttk
from tkinter.font import Font
from tkinter.scrolledtext import ScrolledText

from .config import Config, load_config, resolve_config_path, save_config
from .csv_converter import CSVConverter, CSVConversionError
from .processor import ProcessSession, default_output_dir

CONFIG_PATH = resolve_config_path()


class FileControlApp:
    """Main application window."""

    def __init__(self, root: Tk, initial_path: str | None = None) -> None:
        self.root = root
        self.root.title("File Control")
        self.root.geometry("760x640")
        self.root.minsize(680, 560)

        self.config = load_config(CONFIG_PATH)
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.session: ProcessSession | None = None

        self.input_var = StringVar(value=initial_path or "")
        self.extensions_var = StringVar(value=", ".join(self.config.allowed_extensions))
        self.max_file_var = StringVar(value=str(self.config.max_file_size_mb))
        self.max_zip_var = StringVar(value=str(self.config.max_zip_size_mb))
        self.prefix_var = StringVar(value=self.config.archive_prefix)
        self.recurse_var = BooleanVar(value=self.config.recurse_zips)
        self.convert_var = BooleanVar(value=self.config.convert_unsupported)

        self._build_ui()
        self.root.after(100, self._drain_log)

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        ttk.Label(main, text="Folder or zip to check:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(main, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", **pad)
        btns = ttk.Frame(main)
        btns.grid(row=0, column=2, sticky="e", **pad)
        ttk.Button(btns, text="Folder…", command=self._pick_folder).pack(side="left", padx=2)
        ttk.Button(btns, text="Zip…", command=self._pick_zip).pack(side="left", padx=2)

        ttk.Label(
            main,
            text="Output: a '<name>_NEW' folder will be created next to the input.",
        ).grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        params = ttk.LabelFrame(main, text="Settings", padding=10)
        params.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        params.columnconfigure(1, weight=1)

        ttk.Label(params, text="Allowed formats (comma-separated):").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(params, textvariable=self.extensions_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=4
        )

        ttk.Label(params, text="Max size per file (MB):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(params, textvariable=self.max_file_var, width=10).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(params, text="Max size per zip (MB):").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(params, textvariable=self.max_zip_var, width=10).grid(row=1, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(params, text="Archive prefix:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(params, textvariable=self.prefix_var, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(
            params, text="Explore nested zips", variable=self.recurse_var
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(
            params,
            text="Convert unsupported formats (LibreOffice)",
            variable=self.convert_var,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        ttk.Button(params, text="Save configuration", command=self._save_config).grid(
            row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(8, 2)
        )

        actions = ttk.Frame(main)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        bold_font = Font(family="Segoe UI", size=11, weight="bold")
        self.run_button = Button(
            actions,
            text="Start check",
            command=self._run,
            font=bold_font,
            bg="#0078D4",
            fg="white",
            padx=16,
            pady=8,
            relief="raised",
            bd=2,
            cursor="hand2",
            activebackground="#005A9E",
            activeforeground="white",
        )
        self.run_button.pack(side="left")
        self.progress = ttk.Progressbar(actions, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        ttk.Label(main, text="Log:").grid(row=4, column=0, sticky="w", padx=8)
        self.log_widget = ScrolledText(main, height=16, state="disabled", wrap="word")
        self.log_widget.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        main.rowconfigure(5, weight=1)

    def _pick_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose a folder to check")
        if path:
            self.input_var.set(path)

    def _pick_zip(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a zip to check", filetypes=[("Zip archives", "*.zip")]
        )
        if path:
            self.input_var.set(path)

    def _collect_config(self) -> Config:
        extensions = [e.strip() for e in self.extensions_var.get().split(",") if e.strip()]
        return Config(
            allowed_extensions=extensions,
            max_file_size_mb=float(self.max_file_var.get()),
            max_zip_size_mb=float(self.max_zip_var.get()),
            recurse_zips=self.recurse_var.get(),
            convert_unsupported=self.convert_var.get(),
            archive_prefix=self.prefix_var.get().strip() or "archive",
        )

    def _save_config(self) -> None:
        try:
            config = self._collect_config()
        except ValueError:
            messagebox.showerror("Error", "Sizes must be numbers.")
            return
        save_config(config, CONFIG_PATH)
        self.config = config
        self._log("Configuration saved.")

    def _run(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showwarning("Missing input", "Select a folder or a zip.")
            return

        output_path = str(default_output_dir(input_path))

        try:
            config = self._collect_config()
        except ValueError:
            messagebox.showerror("Error", "Sizes must be numbers.")
            return

        self._clear_log()
        self.run_button.config(state="disabled")
        self.progress.start(12)

        self.worker = threading.Thread(
            target=self._worker_analyze, args=(input_path, output_path, config), daemon=True
        )
        self.worker.start()

    def _worker_analyze(self, input_path: str, output_path: str, config: Config) -> None:
        try:
            self.session = ProcessSession(input_path, output_path, config, log=self.log_queue.put)
            self.session.analyze()
            self.log_queue.put("")
            self.log_queue.put(self.session.rejected_listing())
            self.log_queue.put("")
            self.log_queue.put(self.session.summary.as_text())
            self.log_queue.put("__ANALYZED__")
        except Exception as exc:  # noqa: BLE001
            self.session = None
            self.log_queue.put(f"ERROR: {exc}")
            self.log_queue.put("__DONE__")

    def _prompt_pack(self) -> None:
        session = self.session
        if session is None:
            self._close_session()
            return
        if not session.accepted:
            messagebox.showinfo("Analysis complete", "No allowed files to compress.")
            self._close_session()
            return

        message = (
            f"{len(session.accepted)} file(s) allowed to compress.\n"
            f"{session.summary.rejected_files} unsupported file(s).\n\n"
            "Create the zip(s) now?"
        )
        if messagebox.askyesno("Create archives?", message):
            self.progress.start(12)
            self.worker = threading.Thread(target=self._worker_pack, daemon=True)
            self.worker.start()
        else:
            self._log("Archive creation cancelled.")
            self._close_session()

    def _worker_pack(self) -> None:
        try:
            if self.session is not None:
                self.session.create_archives()
                self.log_queue.put(self.session.summary.as_text())
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(f"ERROR: {exc}")
        finally:
            self.log_queue.put("__DONE__")

    def _close_session(self) -> None:
        self.progress.stop()
        self.run_button.config(state="normal")
        if self.session is not None:
            self.session.close()
            self.session = None

    def _drain_log(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "__ANALYZED__":
                    self.progress.stop()
                    self._prompt_pack()
                elif message == "__DONE__":
                    self._close_session()
                else:
                    self._log(message)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _log(self, message: str) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def _clear_log(self) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")


class MenuApp:
    """Main menu screen for selecting between File Control and CSV Converter."""

    def __init__(self, root: Tk, initial_path: str | None = None) -> None:
        self.root = root
        self.root.title("File Control - Main Menu")
        self.root.geometry("600x400")
        self.root.minsize(400, 300)
        self.initial_path = initial_path
        self.current_app: FileControlApp | CSVConverterApp | None = None

        self._build_menu()

    def _build_menu(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title("File Control - Main Menu")

        main = ttk.Frame(self.root, padding=40)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        title_font = Font(family="Segoe UI", size=18, weight="bold")
        ttk.Label(main, text="File Control", font=title_font).grid(
            row=0, column=0, pady=(0, 30), sticky="ew"
        )

        desc_font = Font(family="Segoe UI", size=11)
        ttk.Label(
            main,
            text="Select a function:",
            font=desc_font,
        ).grid(row=1, column=0, pady=(0, 20), sticky="w")

        buttons_frame = ttk.Frame(main)
        buttons_frame.grid(row=2, column=0, sticky="ew", pady=10)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        btn_font = Font(family="Segoe UI", size=10, weight="bold")
        btn1 = Button(
            buttons_frame,
            text="1. File Control",
            command=self._launch_file_control,
            font=btn_font,
            bg="#0078D4",
            fg="white",
            padx=20,
            pady=12,
            relief="raised",
            bd=2,
            cursor="hand2",
            activebackground="#005A9E",
            activeforeground="white",
            wraplength=200,
            justify="center",
            height=3,
        )
        btn1.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        desc1_font = Font(family="Segoe UI", size=9)
        ttk.Label(
            buttons_frame,
            text="Organize and compress files.\nAnalyze folders/zips and create archives\nwith allowed file types.",
            font=desc1_font,
            justify="left",
        ).grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

        btn2 = Button(
            buttons_frame,
            text="2. CSV Converter",
            command=self._launch_csv_converter,
            font=btn_font,
            bg="#107C10",
            fg="white",
            padx=20,
            pady=12,
            relief="raised",
            bd=2,
            cursor="hand2",
            activebackground="#0D6C0B",
            activeforeground="white",
            wraplength=200,
            justify="center",
            height=3,
        )
        btn2.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        desc2_font = Font(family="Segoe UI", size=9)
        ttk.Label(
            buttons_frame,
            text="Convert between file formats.\nConvert to/from CSV, Excel, PDF,\nJSON, and more.",
            font=desc2_font,
            justify="left",
        ).grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")

        buttons_frame.rowconfigure(0, weight=1)
        buttons_frame.rowconfigure(1, weight=0)

    def _launch_file_control(self) -> None:
        self.current_app = FileControlApp(self.root, initial_path=self.initial_path)
        self.root.title("File Control")

    def _launch_csv_converter(self) -> None:
        self.current_app = CSVConverterApp(self.root)
        self.root.title("CSV Converter")


class CSVConverterApp:
    """CSV Converter application window."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("CSV Converter")
        self.root.geometry("700x700")
        self.root.minsize(600, 500)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.converter: CSVConverter | None = None

        self.input_var = StringVar(value="")
        self.output_format_var = StringVar(value=".csv")
        self.conversion_type_var = StringVar(value="to_csv")

        self._build_ui()
        self.root.after(100, self._drain_log)

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        row = 0

        title_font = Font(family="Segoe UI", size=14, weight="bold")
        ttk.Label(main, text="CSV File Converter", font=title_font).grid(
            row=row, column=0, columnspan=3, sticky="w", **pad
        )
        row += 1

        ttk.Label(main, text="Conversion type:").grid(row=row, column=0, sticky="w", **pad)
        type_frame = ttk.Frame(main)
        type_frame.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Radiobutton(
            type_frame,
            text="Convert to CSV",
            variable=self.conversion_type_var,
            value="to_csv",
            command=self._on_type_changed,
        ).pack(side="left", padx=5)

        ttk.Radiobutton(
            type_frame,
            text="Convert from CSV",
            variable=self.conversion_type_var,
            value="from_csv",
            command=self._on_type_changed,
        ).pack(side="left", padx=5)
        row += 1

        ttk.Label(main, text="Input file:").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(main, textvariable=self.input_var).grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse…", command=self._pick_file).grid(row=row, column=2, sticky="e", **pad)
        row += 1

        self.format_label = ttk.Label(main, text="Output format:")
        self.format_label.grid(row=row, column=0, sticky="w", **pad)

        self.format_frame = ttk.Frame(main)
        self.format_frame.grid(row=row, column=1, columnspan=2, sticky="ew", **pad)

        self.format_combobox = ttk.Combobox(
            self.format_frame,
            textvariable=self.output_format_var,
            state="readonly",
            width=20,
        )
        self.format_combobox.pack(side="left", fill="x", expand=True)

        self._update_format_options()
        row += 1

        self.info_label = ttk.Label(main, text="", foreground="gray", wraplength=600)
        self.info_label.grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        row += 1

        actions = ttk.Frame(main)
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        bold_font = Font(family="Segoe UI", size=11, weight="bold")
        self.convert_button = Button(
            actions,
            text="Convert",
            command=self._convert,
            font=bold_font,
            bg="#0078D4",
            fg="white",
            padx=16,
            pady=8,
            relief="raised",
            bd=2,
            cursor="hand2",
            activebackground="#005A9E",
            activeforeground="white",
        )
        self.convert_button.pack(side="left")

        self.progress = ttk.Progressbar(actions, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)
        row += 1

        ttk.Label(main, text="Log:").grid(row=row, column=0, sticky="w", padx=8)
        row += 1

        self.log_widget = ScrolledText(main, height=12, state="disabled", wrap="word")
        self.log_widget.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        main.rowconfigure(row, weight=1)

    def _on_type_changed(self) -> None:
        self._update_format_options()
        self._clear_log()
        self.input_var.set("")

    def _update_format_options(self) -> None:
        if self.conversion_type_var.get() == "to_csv":
            self.format_label.grid_remove()
            self.format_frame.grid_remove()
            supported = ", ".join(CSVConverter.SUPPORTED_INPUT_FORMATS.keys())
            self.info_label.config(text=f"Supported input formats: {supported}")
        else:
            self.format_label.grid()
            self.format_frame.grid()
            self.format_combobox["values"] = tuple(CSVConverter.SUPPORTED_OUTPUT_FORMATS.keys())
            self.output_format_var.set(".xlsx")
            self.info_label.config(text="Input must be a CSV file")

    def _pick_file(self) -> None:
        if self.conversion_type_var.get() == "to_csv":
            filetypes = [
                ("All supported", ("*.csv", "*.xlsx", "*.xls", "*.json", "*.txt", "*.tsv", "*.ods")),
                ("CSV files", "*.csv"),
                ("Excel files", ("*.xlsx", "*.xls")),
                ("JSON files", "*.json"),
                ("Text files", ("*.txt", "*.tsv")),
                ("All files", "*.*"),
            ]
            title = "Choose a file to convert to CSV"
        else:
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
            title = "Choose a CSV file to convert"

        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if path:
            self.input_var.set(path)

    def _convert(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        input_file = self.input_var.get().strip()
        if not input_file:
            messagebox.showwarning("Missing input", "Select a file to convert.")
            return

        self._clear_log()
        self.convert_button.config(state="disabled")
        self.progress.start(12)

        if self.conversion_type_var.get() == "to_csv":
            self.worker = threading.Thread(
                target=self._worker_to_csv,
                args=(input_file,),
                daemon=True,
            )
        else:
            output_format = self.output_format_var.get()
            self.worker = threading.Thread(
                target=self._worker_from_csv,
                args=(input_file, output_format),
                daemon=True,
            )

        self.worker.start()

    def _worker_to_csv(self, input_file: str) -> None:
        try:
            self.converter = CSVConverter(log=self.log_queue.put)
            output_file = self.converter.convert_to_csv(input_file)
            self.log_queue.put("\nConversion successful!")
            self.log_queue.put(f"Output file: {output_file}")
        except CSVConversionError as exc:
            self.log_queue.put(f"ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(f"ERROR: Unexpected error: {exc}")
        finally:
            self.log_queue.put("__DONE__")

    def _worker_from_csv(self, csv_file: str, output_format: str) -> None:
        try:
            self.converter = CSVConverter(log=self.log_queue.put)
            output_file = self.converter.convert_csv_to_format(csv_file, output_format)
            self.log_queue.put("\nConversion successful!")
            self.log_queue.put(f"Output file: {output_file}")
        except CSVConversionError as exc:
            self.log_queue.put(f"ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(f"ERROR: Unexpected error: {exc}")
        finally:
            self.log_queue.put("__DONE__")

    def _drain_log(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "__DONE__":
                    self._close_conversion()
                else:
                    self._log(message)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _log(self, message: str) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def _clear_log(self) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")

    def _close_conversion(self) -> None:
        self.progress.stop()
        self.convert_button.config(state="normal")
        self.converter = None


def launch(initial_path: str | None = None) -> None:
    """Launch the graphical application."""
    root = Tk()
    MenuApp(root, initial_path=initial_path)
    root.mainloop()
