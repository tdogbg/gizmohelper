#!/usr/bin/env python3
"""
Gizmo GCSE Answer Helper - Powered by Groq
Press the button when you see a question - it reads your screen and gives the answer.
Supports: AQA GCSE Biology, Chemistry, Physics, Geography, English Language & Literature
"""

import tkinter as tk
import threading
import base64
import json
import subprocess
import http.client
import ssl
import os
import time

# ============================================================
#   PASTE YOUR GROQ API KEY HERE (between the quotes)
#   Get one free at console.groq.com
# ============================================================
API_KEY = "your_groq_api_key_here"
# ============================================================

SYSTEM_PROMPT = """You are an expert AQA GCSE tutor specialising in:
- Biology, Chemistry, Physics (Combined & Triple Science)
- Geography
- English Language
- English Literature

You will be shown a screenshot of a Gizmo flashcard/quiz question.

Your job:
1. Read the question carefully
2. If it's multiple choice, identify which option is correct and state the full answer text
3. If it's a written/typed answer, give a concise correct answer

Respond in this exact format:
ANSWER: [the correct answer - include the letter AND full text if multiple choice]
WHY: [one sentence explanation]

Be concise. AQA GCSE level only. If there is no question visible, respond with:
ANSWER: No question found
WHY: Point your screen at a Gizmo question and try again."""


def take_screenshot():
    try:
        subprocess.run(
            ["screencapture", "-x", "-t", "png", "/tmp/gizmo_screen.png"],
            capture_output=True, timeout=5
        )
        with open("/tmp/gizmo_screen.png", "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def ask_groq(image_b64):
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 200,
        "temperature": 0.1
    }

    body = json.dumps(payload).encode("utf-8")

    try:
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.groq.com", context=ctx)
        conn.request(
            "POST",
            "/openai/v1/chat/completions",
            body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }
        )
        response = conn.getresponse()
        response_body = response.read().decode("utf-8")

        if response.status == 200:
            result = json.loads(response_body)
            return result["choices"][0]["message"]["content"]
        elif response.status == 401:
            return "ANSWER: Invalid API key\nWHY: Check your Groq key is correct on line 17."
        elif response.status == 429:
            return "ANSWER: Rate limit\nWHY: Wait a moment and try again."
        elif response.status == 403:
            return f"ANSWER: Access denied\nWHY: Error {response.status} - {response_body[:100]}"
        else:
            return f"ANSWER: Error {response.status}\nWHY: {response_body[:100]}"
    except Exception as e:
        return f"ANSWER: Connection error\nWHY: {str(e)}"
    finally:
        conn.close()


def parse_response(text):
    answer = ""
    why = ""
    for line in text.strip().split("\n"):
        if line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "").strip()
        elif line.startswith("WHY:"):
            why = line.replace("WHY:", "").strip()
    if not answer:
        answer = text.strip()[:120]
    return answer, why


class GizmoHelper:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gizmo Helper")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg="#1a1a2e")
        self.root.geometry("450x250")

        self.busy = False
        self.drag_data = {"x": 0, "y": 0, "dragging": False}
        self.title_frame = None
        self.title_label = None
        self.status_label = None
        self.current_answer = ""

        self.setup_ui()

        # Use AppleScript to position window on active screen
        self.position_with_applescript()

        # Bind drag to entire root window
        self.root.bind("<Button-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<ButtonRelease-1>", self.on_release)

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.mainloop()

    def position_with_applescript(self):
        """Use AppleScript to get mouse position and bring window to front"""
        try:
            result = subprocess.run(
                ["osascript", "-e", "tell application \"System Events\" to return position of mouse"],
                capture_output=True, text=True, timeout=2
            )
            
            if result.stdout:
                coords = result.stdout.strip().split(", ")
                x = int(coords[0]) - 200
                y = int(coords[1]) - 80
                self.root.geometry(f"450x250+{x}+{y}")
            
            self.root.lift()
            self.root.attributes("-topmost", True)
            
        except Exception as e:
            print(f"AppleScript positioning failed: {e}")
            self.root.geometry("450x250+100+100")

    def on_press(self, event):
        """Record initial mouse position for dragging"""
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root
        self.drag_data["dragging"] = True

    def on_drag(self, event):
        """Handle window dragging"""
        if not self.drag_data["dragging"]:
            return

        dx = event.x_root - self.drag_data["x"]
        dy = event.y_root - self.drag_data["y"]

        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy

        self.root.geometry(f"+{x}+{y}")

        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def on_release(self, event):
        """Stop dragging"""
        self.drag_data["dragging"] = False

    def copy_answer(self):
        """Copy answer to clipboard"""
        if self.current_answer:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_answer)
            self.root.update()
            self.status_label.config(text="copied!", fg="#4ecca3")
            self.root.after(1500, lambda: self.status_label.config(text="ready", fg="#4ecca3"))

    def setup_ui(self):
        self.title_frame = tk.Frame(self.root, bg="#16213e", pady=8)
        self.title_frame.pack(fill="x")

        self.title_label = tk.Label(
            self.title_frame, text="Gizmo GCSE Helper",
            bg="#16213e", fg="#e94560",
            font=("Helvetica", 12, "bold")
        )
        self.title_label.pack(side="left", padx=12)

        self.status_label = tk.Label(
            self.title_frame, text="ready",
            bg="#16213e", fg="#4ecca3",
            font=("Helvetica", 9)
        )
        self.status_label.pack(side="right", padx=12)

        answer_frame = tk.Frame(self.root, bg="#1a1a2e", padx=12, pady=8)
        answer_frame.pack(fill="both", expand=True)

        self.answer_label = tk.Label(
            answer_frame,
            text="Press the button when you see a question!",
            bg="#1a1a2e", fg="#ffffff",
            font=("Helvetica", 13, "bold"),
            wraplength=400,
            justify="left"
        )
        self.answer_label.pack(anchor="w")

        self.why_label = tk.Label(
            answer_frame,
            text="",
            bg="#1a1a2e", fg="#a0a0c0",
            font=("Helvetica", 10),
            wraplength=400,
            justify="left"
        )
        self.why_label.pack(anchor="w", pady=(4, 0))

        button_frame = tk.Frame(self.root, bg="#1a1a2e")
        button_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.btn = tk.Button(
            button_frame,
            text="GET ANSWER",
            command=self.on_button_click,
            bg="#00D9FF", fg="#000000",
            font=("Helvetica", 13, "bold"),
            relief="flat",
            cursor="hand2",
            pady=8
        )
        self.btn.pack(side="left", fill="both", expand=True, padx=(0, 6))

        copy_btn = tk.Button(
            button_frame,
            text="COPY",
            command=self.copy_answer,
            bg="#4ecca3", fg="#000000",
            font=("Helvetica", 11, "bold"),
            relief="flat",
            cursor="hand2",
            pady=8,
            width=8
        )
        copy_btn.pack(side="left")

    def on_button_click(self):
        if self.busy:
            return
        self.busy = True
        self.btn.config(state="disabled", text="Thinking...")
        self.status_label.config(text="working...", fg="#f5a623")
        self.answer_label.config(text="Reading your screen...")
        self.why_label.config(text="")
        threading.Thread(target=self.fetch_answer, daemon=True).start()

    def fetch_answer(self):
        image_b64 = take_screenshot()
        if image_b64 is None:
            self.root.after(0, lambda: self.show_result("Screenshot failed", "Could not capture screen. Try again."))
            return
        response = ask_groq(image_b64)
        answer, why = parse_response(response)
        self.root.after(0, lambda: self.show_result(answer, why))

    def show_result(self, answer, why):
        self.current_answer = answer
        self.answer_label.config(text=answer)
        self.why_label.config(text=why)
        self.status_label.config(text="ready", fg="#4ecca3")
        self.btn.config(state="normal", text="GET ANSWER")
        self.busy = False


if __name__ == "__main__":
    if API_KEY == "your_groq_api_key_here":
        print("\n  Please add your Groq API key to the file!\n")
    else:
        print("Starting Gizmo Helper...")
        print("Press GET ANSWER whenever you see a Gizmo question.\n")
        GizmoHelper()
