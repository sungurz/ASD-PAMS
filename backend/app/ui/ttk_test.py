"""Quick smoke-test — run with:  python ttk_test.py"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *

app = tb.Window(themename="darkly")
app.title("ttkbootstrap Test")
app.geometry("320x140")

tb.Label(
    app, text="✅  ttkbootstrap is working!",
    font=("Helvetica", 14, "bold"),
).pack(expand=YES)

tb.Button(app, text="Close", bootstyle="primary", command=app.destroy).pack(pady=(0, 16))

app.mainloop()