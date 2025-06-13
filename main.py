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

    def get_appointments(self, user_id=None, search=None):
        query = (
            "SELECT a.id, u.nome, a.data, a.hora, a.criado_em"
            " FROM appointments a JOIN users u ON a.user_id=u.id"
        )
        params = []
        if user_id:
            query += " WHERE a.user_id = ?"
            params.append(user_id)
        if search:
            prefix = " AND" if 'WHERE' in query else " WHERE"
            query += f"{prefix} (u.nome LIKE ? OR a.data LIKE ?)"
            params.extend((f"%{search}%", f"%{search}%"))
        query += (
            " ORDER BY substr(a.data, 7, 4) || '-' || substr(a.data, 4, 2) || '-' || substr(a.data, 1, 2), a.hora"
        )
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


class Validator:
    @staticmethod
    def _validate_date(entry, show=True):
        txt = entry.get().replace('/', '')[:8]
        if len(txt) > 2: txt = f"{txt[:2]}/{txt[2:]}"
        if len(txt) > 5: txt = f"{txt[:5]}/{txt[5:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)
        if len(txt) < 10: return True
        try:
            date_obj = datetime.strptime(txt, "%d/%m/%Y").date()
            if date_obj < date.today(): raise ValueError
            return True
        except ValueError:
            if show: messagebox.showwarning("Erro", "Data inválida ou no passado.")
            return False

    @staticmethod
    def _validate_time(entry, show=True):
        txt = entry.get().replace(':', '')[:4]
        if len(txt) > 2: txt = f"{txt[:2]}:{txt[2:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)
        if len(txt) < 5: return True
        try:
            input_time = datetime.strptime(txt, "%H:%M").time()
            parent = entry.master; date_entry = None
            for child in parent.winfo_children():
                if isinstance(child, ttk.Entry) and child != entry:
                    date_entry = child; break
            if date_entry:
                input_date = datetime.strptime(date_entry.get(), "%d/%m/%Y").date()
                if input_date == date.today() and input_time <= datetime.now().time():
                    raise ValueError
            return True
        except Exception:
            if show: messagebox.showwarning("Erro", "Hora inválida ou no passado.")
            return False


class AppointmentWindow(tk.Toplevel):
    def __init__(self, master, db, user=None):
        super().__init__(master)
        self.db = db; self.user = user
        self.title(f"Agendamentos{' - ' + user[1] if user else ''}")
        self.geometry("980x660")
        # Campo de busca para o dono
        if not user:
            sf = ttk.Frame(self); sf.pack(fill=tk.X, pady=5, padx=5)
            tk.Label(sf, text="Buscar:").pack(side=tk.LEFT)
            self.search_var = tk.StringVar()
            tk.Entry(sf, textvariable=self.search_var).pack(side=tk.LEFT, padx=5)
            ttk.Button(sf, text="Pesquisar", command=self.refresh).pack(side=tk.LEFT)

        # Notebook interno: Futuros / Passados
        inner_nb = ttk.Notebook(self); inner_nb.pack(expand=True, fill='both', pady=5, padx=5)
        self.frames = {}
        for tab in ("Futuros", "Passados"):
            frm = ttk.Frame(inner_nb); inner_nb.add(frm, text=tab)
            tv = ttk.Treeview(frm, columns=("ID","Nome","Data","Hora","Criado em"), show="headings")
            for col in ("ID","Nome","Data","Hora","Criado em"):
                tv.heading(col, text=col); tv.column(col, anchor="center")
            tv.pack(expand=True, fill='both')
            self.frames[tab] = tv

        # Botões de ação
        btns = ttk.Frame(self); btns.pack(pady=5)
        if user:
            ttk.Button(btns, text="Adicionar", command=self.add).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Editar", command=self.edit).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Excluir", command=self.delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.refresh()

    def refresh(self):
        # limpa
        for tv in self.frames.values():
            for iid in tv.get_children(): tv.delete(iid)
        # busca e classifica
        term = self.search_var.get().strip() if hasattr(self, 'search_var') else None
        appts = self.db.get_appointments(user_id=(self.user[0] if self.user else None), search=term)
        for a in appts:
            appt_date = datetime.strptime(a[2], "%d/%m/%Y").date()
            tab = "Futuros" if appt_date >= date.today() else "Passados"
            self.frames[tab].insert("", tk.END, values=a)

    def add(self): self._open_form('add')
    def edit(self):
        # procura seleção em ambos
        for tv in self.frames.values():
            sel = tv.focus()
            if sel:
                vals = tv.item(sel, 'values')
                return self._open_form('edit', vals)
    def delete(self):
        for tv in self.frames.values():
            sel = tv.focus()
            if sel and messagebox.askyesno("Confirmar", "Excluir agendamento?", parent=self):
                self.db.delete_appointment(tv.item(sel)['values'][0])
                return self.refresh()

    def _open_form(self, mode, appt=None):
        form = tk.Toplevel(self); form.title("Agendamento")
        entries = {}
        for label, validator in [('Data (DD/MM/AAAA)', Validator._validate_date), ('Hora (HH:MM)', Validator._validate_time)]:
            ttk.Label(form, text=label).pack(pady=2)
            e = ttk.Entry(form); e.pack(pady=2)
            e.bind('<KeyRelease>', lambda ev, e=e, v=validator: v(e))
            entries[label] = e
        if appt:
            entries['Data (DD/MM/AAAA)'].insert(0, appt[2])
            entries['Hora (HH:MM)'].insert(0, appt[3])

        def confirm():
            d = entries['Data (DD/MM/AAAA)'].get().strip()
            h = entries['Hora (HH:MM)'].get().strip()
            if not Validator._validate_date(entries['Data (DD/MM/AAAA)'], show=False) \
               or not Validator._validate_time(entries['Hora (HH:MM)'], show=False):
                return
            if mode == 'add':
                self.db.add_appointment(self.user[0], d, h)
            else:
                self.db.update_appointment(appt[0], d, h)
            form.destroy(); self.refresh()

        ttk.Button(form, text="Confirmar", command=confirm).pack(pady=5)


class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Sistema de Login e Cadastro")
        self.geometry("980x660")
        self.resizable(False, False)

        try:
            self.iconphoto(False, tk.PhotoImage(file="imagens/icon.png"))
        except:
            pass
        try:
            bg = Image.open("imagens/background.png").resize((980,660), Image.LANCZOS)
            self._bg = ImageTk.PhotoImage(bg)
            tk.Label(self, image=self._bg).place(relwidth=1, relheight=1)
        except:
            pass

        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        panels = [
            ('Login', [('E-mail', False), ('Senha', True)], self._do_login),
            ('Cadastro', [('Nome', False), ('E-mail', False), ('Telefone', False), ('Senha', True)], self._do_register)
        ]
        for title, fields, action in panels:
            frame = ttk.Frame(nb); entries = {}
            for label, pwd in fields:
                ttk.Label(frame, text=label + ":").pack(pady=3)
                e = ttk.Entry(frame, show='*' if pwd else ''); e.pack()
                entries[label] = e
            ttk.Button(frame, text=title, command=lambda e=entries, a=action: a(e)).pack(pady=10)
            nb.add(frame, text=title)
        nb.place(relx=0.5, rely=0.5, anchor='center', width=300, height=300)

    def _do_register(self, entries):
        nome = entries['Nome'].get().strip()
        email = entries['E-mail'].get().strip()
        tel = entries['Telefone'].get().strip()
        pwd = entries['Senha'].get().strip()
        if not nome or not re.match(r"[^@]+@[^@]+\.[^@]+", email) or not pwd:
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
