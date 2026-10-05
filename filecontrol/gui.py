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

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # Input
        ttk.Label(main, text="Folder or zip to check:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(main, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", **pad)
        btns = ttk.Frame(main)
        btns.grid(row=0, column=2, sticky="e", **pad)
        ttk.Button(btns, text="Folder…", command=self._pick_folder).pack(side="left", padx=2)
        ttk.Button(btns, text="Zip…", command=self._pick_zip).pack(side="left", padx=2)

        # Note about the automatic output
        ttk.Label(
            main,
            text="Output: a “<name>_NEW” folder will be created next to the input.",
        ).grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        # Settings
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

        # Actions
        actions = ttk.Frame(main)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        # Premium styled button for Start Check
        bold_font = Font(family="Segoe UI", size=11, weight="bold")
        self.run_button = Button(
            actions,
            text="Start check",
            command=self._run,
            font=bold_font,
            bg="#0078D4",  # Windows blue
            fg="white",
            padx=16,
            pady=8,
            relief="raised",
            bd=2,
            cursor="hand2",
            activebackground="#005A9E",  # Darker blue on hover
            activeforeground="white",
        )
        self.run_button.pack(side="left")
        self.progress = ttk.Progressbar(actions, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        # Log
        ttk.Label(main, text="Log:").grid(row=4, column=0, sticky="w", padx=8)
        self.log_widget = ScrolledText(main, height=16, state="disabled", wrap="word")
        self.log_widget.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        main.rowconfigure(5, weight=1)

    # -------------------------------------------------------------- Pickers
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

    # --------------------------------------------------------------- Config
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

    # ------------------------------------------------------------- Execution
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
        """Step 1: analyze and list the unsupported files."""
        try:
            self.session = ProcessSession(input_path, output_path, config, log=self.log_queue.put)
            self.session.analyze()
            self.log_queue.put("")
            self.log_queue.put(self.session.rejected_listing())
            self.log_queue.put("")
            self.log_queue.put(self.session.summary.as_text())
            self.log_queue.put("__ANALYZED__")
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.session = None
            self.log_queue.put(f"ERROR: {exc}")
            self.log_queue.put("__DONE__")

    def _prompt_pack(self) -> None:
        """Step 2: ask for confirmation before creating the archives."""
        session = self.session
        if session is None:
            self._close_session()
            return
        if not session.accepted:
            messagebox.showinfo(
                "Analysis complete", "No allowed files to compress."
            )
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
        """Compress the allowed files after confirmation."""
        try:
            if self.session is not None:
                self.session.create_archives()
                self.log_queue.put(self.session.summary.as_text())
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.log_queue.put(f"ERROR: {exc}")
        finally:
            self.log_queue.put("__DONE__")

    def _close_session(self) -> None:
        """Clean up the session and re-enable the start button."""
        self.progress.stop()
        self.run_button.config(state="normal")
        if self.session is not None:
            self.session.close()
            self.session = None

    # ------------------------------------------------------------- Log
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


def launch(initial_path: str | None = None) -> None:
    """Launch the graphical application."""
    root = Tk()
    FileControlApp(root, initial_path=initial_path)
    root.mainloop()
