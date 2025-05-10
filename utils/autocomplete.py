# utils/autocomplete_entry.py
import customtkinter as ctk
import tkinter as tk

class AutocompleteEntry(ctk.CTkEntry):
    def __init__(self, master=None, values=None, **kwargs):
        super().__init__(master, **kwargs)
        self._completion_list = values if values else []
        self._popup = None

        self.bind("<KeyRelease>", self._on_keyrelease)
        self.bind("<FocusOut>", self._on_focus_out)

    def set_completion_list(self, values):
        self._completion_list = values

    def _on_focus_out(self, event):
        if self._popup:
            self._popup.destroy()
            self._popup = None

    def _on_keyrelease(self, event):
        text = self.get().lower()
        if not text:
            matches = self._completion_list
        else:
            matches = [v for v in self._completion_list if text in v.lower()]

        if not matches:
            if self._popup:
                self._popup.destroy()
                self._popup = None
            return

        if not self._popup:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            self._popup.attributes("-topmost", True)

            self.listbox = tk.Listbox(self._popup, height=6)
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.listbox.delete(0, "end")
        for m in matches[:10]:
            self.listbox.insert("end", m)

        # 위치 업데이트
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self._popup.geometry(f"+{x}+{y}")

    def _on_select(self, event):
        if not self._popup:
            return
        idx = self.listbox.curselection()
        if not idx:
            return
        value = self.listbox.get(idx[0])
        self.delete(0, "end")
        self.insert(0, value)

        self._popup.destroy()
        self._popup = None
