import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sqlite3
import re
import hashlib
from datetime import datetime

DB_FILE = "app.db"
EMAIL_DONO = "sam@s.com"
SENHA_DONO_HASH = hashlib.sha256("12345".encode()).hexdigest()

class Database:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._initialize()

    def _initialize(self):
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefone TEXT,
            senha_hash TEXT NOT NULL,
            criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.executescript(schema)

    def add_user(self, nome, email, telefone, senha_hash):
        criado = datetime.now().isoformat()
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO users (nome, email, telefone, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
                (nome, email, telefone, senha_hash, criado)
            )

    def get_user_by_email(self, email):
        with sqlite3.connect(self.db_file) as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def add_appointment(self, user_id, data, hora):
        criado = datetime.now().isoformat()
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO appointments (user_id, data, hora, criado_em) VALUES (?, ?, ?, ?)",
                (user_id, data, hora, criado)
            )

    def get_appointments(self, user_id=None):
        query = (
            "SELECT a.id, u.nome, a.data, a.hora, a.criado_em"
            " FROM appointments a JOIN users u ON a.user_id=u.id"
        )
        params = ()
        if user_id:
            query += " WHERE user_id = ?"
            params = (user_id,)
        with sqlite3.connect(self.db_file) as conn:
            return conn.execute(query, params).fetchall()

    def update_appointment(self, appt_id, data, hora):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "UPDATE appointments SET data = ?, hora = ? WHERE id = ?",
                (data, hora, appt_id)
            )

    def delete_appointment(self, appt_id):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))

class AppointmentWindow(tk.Toplevel):
    def __init__(self, master, db, user=None):
        super().__init__(master)
        self.db = db
        self.user = user
        self.title(f"Agendamentos{' - ' + user[1] if user else ''}")
        self.geometry("600x400")

        # Columns definition
        cols = ("ID", "Data", "Hora", "Criado em") if user else ("ID", "Nome", "Data", "Hora", "Criado em")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.pack(expand=True, fill="both")

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        if user:
            ttk.Button(btns, text="Adicionar", command=self.add).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Editar", command=self.edit).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Excluir", command=self.delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for a in self.db.get_appointments(user_id=self.user[0] if self.user else None):
            self.tree.insert("", tk.END, values=a)

    def add(self): self._open_form('add')
    def edit(self):
        sel = self.tree.focus()
        if sel: self._open_form('edit', self.tree.item(sel)['values'])
    def delete(self):
        sel = self.tree.focus()
        if sel and messagebox.askyesno("Confirmar", "Excluir agendamento?", parent=self):
            self.db.delete_appointment(self.tree.item(sel)['values'][0]); self.refresh()

    def _open_form(self, mode, appt=None):
        form = tk.Toplevel(self); form.title("Agendamento")
        fields = [('Data (DD/MM/AAAA)', self._validate_date), ('Hora (HH:MM)', self._validate_time)]
        entries = {}
        for label, validator in fields:
            ttk.Label(form, text=label).pack(pady=2)
            e = ttk.Entry(form); e.pack(pady=2)
            e.bind('<KeyRelease>', lambda ev, e=e, v=validator: v(e))
            entries[label] = e
        if appt:
            entries[fields[0][0]].insert(0, appt[2]); entries[fields[1][0]].insert(0, appt[3])
        def confirm():
            d = entries[fields[0][0]].get().strip(); h = entries[fields[1][0]].get().strip()
            if not self._validate_date(entries[fields[0][0]], show=False) or not self._validate_time(entries[fields[1][0]], show=False): return
            if mode=='add': self.db.add_appointment(self.user[0], d, h)
            else: self.db.update_appointment(appt[0], d, h)
            form.destroy(); self.refresh()
        ttk.Button(form, text="Confirmar", command=confirm).pack(pady=5)

    @staticmethod
    def _validate_date(entry, show=True):
        txt = entry.get().replace('/', '')[:8]
        if len(txt)>2: txt=f"{txt[:2]}/{txt[2:]}"
        if len(txt)>5: txt=f"{txt[:5]}/{txt[5:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)
        try:
            date_obj = datetime.strptime(txt, "%d/%m/%Y").date()
            if date_obj < datetime.today().date(): raise ValueError
            return True
        except:
            if show: messagebox.showwarning("Erro", "Data inválida ou passada.")
            return False

    @staticmethod
    def _validate_time(entry, show=True):
        txt = entry.get().replace(':', '')[:4]
        if len(txt)>2: txt=f"{txt[:2]}:{txt[2:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)
        try:
            datetime.strptime(txt, "%H:%M"); return True
        except:
            if show: messagebox.showwarning("Erro", "Hora inválida.")
            return False

class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Sistema de Login e Cadastro")
        self.geometry("980x660")
        self.resizable(False, False)

        # Load icon
        try: self.iconphoto(False, tk.PhotoImage(file="imagens/icon.png"))
        except: pass

        # Load background
        try:
            bg_img = Image.open("imagens/background.png").resize((980, 660), Image.LANCZOS)
            bg_photo = ImageTk.PhotoImage(bg_img)
            tk.Label(self, image=bg_photo).place(relwidth=1, relheight=1)
            self._bg_photo = bg_photo
        except: pass

        self._build_ui()

    def _build_ui(self):
        # Notebook size reduced to show more background around
        notebook = ttk.Notebook(self)
        tabs = [
            ('Login', [('E-mail', False), ('Senha', True)], self._do_login),
            ('Cadastro', [('Nome', False), ('E-mail', False), ('Telefone', False), ('Senha', True)], self._do_register)
        ]
        for title, fields, action in tabs:
            frame = ttk.Frame(notebook)
            entries = {}
            for label, pwd in fields:
                ttk.Label(frame, text=label+":").pack(pady=3)
                e = ttk.Entry(frame, show='*' if pwd else '')
                e.pack(); entries[label] = e
            ttk.Button(frame, text=title, command=lambda e=entries, a=action: a(e)).pack(pady=5)
            notebook.add(frame, text=title)
        # Place notebook with specific width/height to reveal background
        notebook.place(relx=0.5, rely=0.5, anchor='center', width=250, height=250)

    def _do_register(self, entries):
        nome = entries['Nome'].get().strip(); email = entries['E-mail'].get().strip()
        tel = entries['Telefone'].get().strip(); pwd = entries['Senha'].get().strip()
        if not nome or not email or not pwd or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return messagebox.showwarning("Erro", "Preencha corretamente todos os campos.")
        if self.db.get_user_by_email(email): return messagebox.showwarning("Erro", "E-mail já cadastrado.")
        self.db.add_user(nome, email, tel, hashlib.sha256(pwd.encode()).hexdigest())
        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso.")
        for e in entries.values(): e.delete(0, tk.END)

    def _do_login(self, entries):
        email = entries['E-mail'].get().strip(); pwd = entries['Senha'].get().strip()
        if not email or not pwd: return messagebox.showwarning("Erro", "Preencha todos os campos.")
        if email == EMAIL_DONO and hashlib.sha256(pwd.encode()).hexdigest() == SENHA_DONO_HASH:
            AppointmentWindow(self, self.db)
        else:
            user = self.db.get_user_by_email(email)
            if user and hashlib.sha256(pwd.encode()).hexdigest() == user[4]:
                AppointmentWindow(self, self.db, user)
            else:
                messagebox.showerror("Erro", "E-mail ou senha incorretos.")

if __name__ == "__main__":
    LoginApp().mainloop()
