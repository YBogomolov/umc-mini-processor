import os
import subprocess
from tkinter import Label, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from processor import generate_pdf


class MiniProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Processor")
        self.root.geometry("600x400")

        self.label = Label(
            root, text="Drag & Drop Folder Here", padx=20, pady=50, relief="groove"
        )
        self.label.pack(expand=True, fill="both", padx=10, pady=10)

        self.label.drop_target_register(DND_FILES)  # type: ignore
        self.label.dnd_bind("<<Drop>>", self.handle_drop)  # type: ignore

    def handle_drop(self, event):
        folder_path = event.data.strip("{}")

        if os.path.isdir(folder_path):
            try:
                output_name = f"{os.path.basename(folder_path)}.pdf"
                output_path = os.path.join(folder_path, output_name)
                generate_pdf(folder_path, output_path)

                subprocess.run(["open", output_path])
            except Exception as e:
                messagebox.showerror("Error", f"Processing failed: {str(e)}")
        else:
            messagebox.showwarning("Input Error", "Please drop a folder, not a file.")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MiniProcessorApp(root)
    root.mainloop()
