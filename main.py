import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sqlite3
import re
import hashlib
from datetime import datetime, date

DB_FILE = "app.db"
EMAIL_DONO = "sam@s.com"
SENHA_DONO_HASH = hashlib.sha256("12345".encode()).hexdigest()

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

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

    def get_users_with_appointments(self):
        query = """
        SELECT u.id, u.nome, u.email, u.telefone
        FROM users u
        JOIN appointments a ON u.id = a.user_id
        GROUP BY u.id
        ORDER BY MIN(
            DATE(substr(a.data, 7, 4) || '-' || substr(a.data, 4, 2) || '-' || substr(a.data, 1, 2)) || ' ' || a.hora
        ) ASC
        """
        with sqlite3.connect(self.db_file) as conn:
            return conn.execute(query).fetchall()

class Validator:
    @staticmethod
    def _validate_date(entry, show=True):
        txt = entry.get().replace('/', '')[:8]
        if len(txt) > 2:
            txt = f"{txt[:2]}/{txt[2:]}"
        if len(txt) > 5:
            txt = f"{txt[:5]}/{txt[5:]}"

        entry.delete(0, tk.END)
        entry.insert(0, txt)

        # Só validar a data se estiver completa (10 caracteres: DD/MM/AAAA)
        if len(txt) < 10:
            return True  # Não validar ainda

        try:
            date_obj = datetime.strptime(txt, "%d/%m/%Y").date()
            if date_obj < date.today():
                raise ValueError("Data passada.")
            return True
        except ValueError:
            if show:
                messagebox.showwarning("Erro", "Data inválida ou no passado.")
            return False

    @staticmethod
    def _validate_time(entry, show=True):
        txt = entry.get().replace(':', '')[:4]
        if len(txt) > 2:
            txt = f"{txt[:2]}:{txt[2:]}"

        entry.delete(0, tk.END)
        entry.insert(0, txt)

        # Só validar a hora se estiver completa (5 caracteres: HH:MM)
        if len(txt) < 5:
            return True  # Não validar ainda

        try:
            input_time = datetime.strptime(txt, "%H:%M").time()
            # valida se hora não está no passado para hoje
            parent = entry.master
            date_entry = None
            for child in parent.winfo_children():
                if isinstance(child, ttk.Entry) and child != entry:
                    date_entry = child
            if date_entry:
                try:
                    input_date = datetime.strptime(date_entry.get(), "%d/%m/%Y").date()
                    if input_date == date.today() and input_time <= datetime.now().time():
                        raise ValueError("Hora no passado.")
                except:
                    pass
            return True
        except ValueError:
            if show:
                messagebox.showwarning("Erro", "Hora inválida ou no passado.")
            return False

class AppointmentWindow(tk.Toplevel):
    def __init__(self, master, db, user=None):
        super().__init__(master)
        self.db = db
        self.user = user
        self.title(f"Agendamentos{' - ' + user[1] if user else ''}")
        self.geometry("980x660")

        cols = ("ID", "Nome", "Data", "Hora") if user else ("ID", "Nome", "Data", "Hora", "Criado em")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center")
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
        for i in self.tree.get_children():
            self.tree.delete(i)
        for a in self.db.get_appointments(user_id=self.user[0] if self.user else None):
            self.tree.insert("", tk.END, values=a)

    def add(self):
        self._open_form('add')

    def edit(self):
        sel = self.tree.focus()
        if sel:
            self._open_form('edit', self.tree.item(sel)['values'])

    def delete(self):
        sel = self.tree.focus()
        if sel and messagebox.askyesno("Confirmar", "Excluir agendamento?", parent=self):
            self.db.delete_appointment(self.tree.item(sel)['values'][0])
            self.refresh()

    def _open_form(self, mode, appt=None):
        form = tk.Toplevel(self)
        form.title("Agendamento")

        fields = [
            ('Data (DD/MM/AAAA)', Validator._validate_date),
            ('Hora (HH:MM)', Validator._validate_time)
        ]
        entries = {}
        for label, validator in fields:
            ttk.Label(form, text=label).pack(pady=2)
            e = ttk.Entry(form)
            e.pack(pady=2)
            e.bind('<KeyRelease>', lambda ev, e=e, v=validator: v(e))
            entries[label] = e

        if appt:
            entries[fields[0][0]].insert(0, appt[2])
            entries[fields[1][0]].insert(0, appt[3])

        def confirm():
            d = entries[fields[0][0]].get().strip()
            h = entries[fields[1][0]].get().strip()
            if not Validator._validate_date(entries[fields[0][0]], show=False) or not Validator._validate_time(entries[fields[1][0]], show=False):
                return
            if mode == 'add':
                self.db.add_appointment(self.user[0], d, h)
            else:
                self.db.update_appointment(appt[0], d, h)
            form.destroy()
            self.refresh()

        ttk.Button(form, text="Confirmar", command=confirm).pack(pady=5)

class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Sistema de Login e Cadastro")
        self.geometry("980x660")
        self.resizable(False, False)

        # Load icon
        try:
            self.iconphoto(False, tk.PhotoImage(file="imagens/icon.png"))
        except:
            pass

        # Load background
        try:
            bg_img = Image.open("imagens/background.png").resize((980, 660), Image.LANCZOS)
            bg_photo = ImageTk.PhotoImage(bg_img)
            tk.Label(self, image=bg_photo).place(relwidth=1, relheight=1)
            self._bg_photo = bg_photo
        except:
            pass

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        tabs = [
            ('Login', [('E-mail', False), ('Senha', True)], self._do_login),
            ('Cadastro', [('Nome', False), ('E-mail', False), ('Telefone', False), ('Senha', True)], self._do_register)
        ]
        for title, fields, action in tabs:
            frame = ttk.Frame(notebook)
            entries = {}
            for label, pwd in fields:
                ttk.Label(frame, text=label + ":").pack(pady=3)
                e = ttk.Entry(frame, show='*' if pwd else '')
                e.pack()
                entries[label] = e
            ttk.Button(frame, text=title, command=lambda e=entries, a=action: a(e)).pack(pady=5)
            notebook.add(frame, text=title)

        notebook.place(relx=0.5, rely=0.5, anchor='center', width=250, height=250)

    def _do_register(self, entries):
        nome = entries['Nome'].get().strip()
        email = entries['E-mail'].get().strip()
        tel = entries['Telefone'].get().strip()
        pwd = entries['Senha'].get().strip()

        if not nome or not email or not pwd or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return messagebox.showwarning("Erro", "Preencha corretamente todos os campos.")
        if self.db.get_user_by_email(email):
            return messagebox.showwarning("Erro", "E-mail já cadastrado.")
        self.db.add_user(nome, email, tel, hash_password(pwd))
        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso.")
        for e in entries.values():
            e.delete(0, tk.END)

    def _do_login(self, entries):
        email = entries['E-mail'].get().strip()
        pwd = entries['Senha'].get().strip()

        if not email or not pwd:
            return messagebox.showwarning("Erro", "Preencha todos os campos.")

        if email == EMAIL_DONO and hash_password(pwd) == SENHA_DONO_HASH:
            AppointmentWindow(self, self.db)
        else:
            user = self.db.get_user_by_email(email)
            if user and hash_password(pwd) == user[4]:
                AppointmentWindow(self, self.db, user)
            else:
                messagebox.showerror("Erro", "E-mail ou senha incorretos.")

if __name__ == "__main__":
    LoginApp().mainloop()
