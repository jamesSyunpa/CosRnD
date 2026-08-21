import customtkinter as ctk
from PIL import Image
import os

class HelpViewer(ctk.CTkToplevel):
    def __init__(self, master, image_path=None, title="Help Guide"):
        super().__init__(master)
        
        self.title(title)
        self.geometry("900x650") 
        self.resizable(True, True)
        
        # Center the window
        try:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            self.geometry(f'{width}x{height}+{x}+{y}')
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Image Container (Scrollable if needed, but fitting is better)
        self.image_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.image_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.image_label = ctk.CTkLabel(self.image_frame, text="")
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Footer / Controls
        self.footer_frame = ctk.CTkFrame(self, height=50, fg_color="transparent")
        self.footer_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.close_button = ctk.CTkButton(
            self.footer_frame, 
            text="Close", 
            command=self.destroy,
            width=100
        )
        self.close_button.pack(side="right", padx=10)
        
        # Load the image
        if image_path and os.path.exists(image_path):
            self.load_image(image_path)
        else:
            self.image_label.configure(text="Image not found.")

    def load_image(self, path):
        try:
            pil_image = Image.open(path)
            
            # Simple resizing logic to fit width (approximate)
            # You might want more sophisticated resizing later
            target_width = 800
            w_percent = (target_width / float(pil_image.size[0]))
            h_size = int((float(pil_image.size[1]) * float(w_percent)))
            
            # Use LANCZOS which is high-quality downsampling
            resized_image = pil_image.resize((target_width, h_size), Image.Resampling.LANCZOS)
            
            self.photo_image = ctk.CTkImage(light_image=resized_image, size=(target_width, h_size))
            self.image_label.configure(image=self.photo_image, text="")
            
        except Exception as e:
            self.image_label.configure(text=f"Failed to load image:\n{str(e)}")
            print(f"[HelpViewer] Error loading image: {e}")
