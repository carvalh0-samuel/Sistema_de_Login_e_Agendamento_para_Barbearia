"""Sistema de login, cadastro e agendamentos (Tkinter + SQLite)."""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import tkinter as tk
from contextlib import closing
from datetime import date, datetime
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
DB_FILE = "app.db"

# Credenciais do dono. Para uso real, defina as variáveis de ambiente
# OWNER_EMAIL e OWNER_PASSWORD em vez de deixar valores fixos no código.
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "sam@s.com")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "12345")

PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD_LEN = 6
PANEL_BG = "#f0f0f0"


# ----------------------------------------------------------------------------
# Segurança
# ----------------------------------------------------------------------------
def hash_password(pwd):
    """Gera hash PBKDF2 com salt aleatório: 'pbkdf2$<salt>$<hash>'."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(pwd, stored):
    """Confere a senha. Aceita também o formato antigo (SHA-256 puro)."""
    if stored.startswith("pbkdf2$"):
        try:
            _, salt_hex, digest_hex = stored.split("$")
        except ValueError:
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256", pwd.encode(), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(calc.hex(), digest_hex)
    legacy = hashlib.sha256(pwd.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


def needs_rehash(stored):
    return not stored.startswith("pbkdf2$")


def is_owner(email, pwd):
    ok_email = hmac.compare_digest(email.lower().encode(), OWNER_EMAIL.lower().encode())
    ok_pwd = hmac.compare_digest(pwd.encode(), OWNER_PASSWORD.encode())
    return ok_email and ok_pwd


# ----------------------------------------------------------------------------
# Utilidades de data/hora (funções puras, fáceis de testar)
# ----------------------------------------------------------------------------
def format_date_text(raw):
    """Aplica a máscara DD/MM/AAAA."""
    digits = re.sub(r"\D", "", raw)[:8]
    out = digits[:2]
    if len(digits) > 2:
        out += "/" + digits[2:4]
    if len(digits) > 4:
        out += "/" + digits[4:]
    return out


def format_time_text(raw):
    """Aplica a máscara HH:MM."""
    digits = re.sub(r"\D", "", raw)[:4]
    out = digits[:2]
    if len(digits) > 2:
        out += ":" + digits[2:]
    return out


def parse_date(text):
    return datetime.strptime(text, "%d/%m/%Y").date()


def iso_to_br(iso_text):
    year, month, day = iso_text.split("-")
    return f"{day}/{month}/{year}"


def format_created(iso_text):
    try:
        return datetime.fromisoformat(iso_text).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_text


def validate_slot(date_text, time_text, partial=False):
    """Retorna uma mensagem de erro ou None se estiver tudo certo.

    Com partial=True, campos incompletos não geram erro (feedback enquanto digita).
    """
    day = None
    if len(date_text) == 10:
        try:
            day = parse_date(date_text)
        except ValueError:
            return "Data inválida."
        if day < date.today():
            return "A data não pode estar no passado."
    elif not partial:
        return "Informe a data completa (DD/MM/AAAA)."

    moment = None
    if len(time_text) == 5:
        try:
            moment = datetime.strptime(time_text, "%H:%M").time()
        except ValueError:
            return "Hora inválida."
    elif not partial:
        return "Informe a hora completa (HH:MM)."

    if day and moment and datetime.combine(day, moment) <= datetime.now():
        return "O horário não pode estar no passado."
    return None


# ----------------------------------------------------------------------------
# Banco de dados
# ----------------------------------------------------------------------------
SCHEMA = """
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
    data TEXT NOT NULL,          -- formato ISO: AAAA-MM-DD
    hora TEXT NOT NULL,          -- formato HH:MM
    criado_em TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_appointments_slot ON appointments (data, hora);
"""

# Converte registros antigos (DD/MM/AAAA) para o formato ISO.
MIGRATE_DATES = """
UPDATE appointments
SET data = substr(data, 7, 4) || '-' || substr(data, 4, 2) || '-' || substr(data, 1, 2)
WHERE data LIKE '__/__/____'
"""


def _like(term):
    """Escapa curingas do LIKE para a busca ser literal."""
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


class Database:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _execute(self, sql, params=(), fetch=None):
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.lastrowid

    def _initialize(self):
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            conn.execute(MIGRATE_DATES)

    # --- usuários ---------------------------------------------------------
    def add_user(self, nome, email, telefone, senha_hash):
        return self._execute(
            "INSERT INTO users (nome, email, telefone, senha_hash, criado_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (nome, email, telefone, senha_hash, datetime.now().isoformat()),
        )

    def get_user_by_email(self, email):
        return self._execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)", (email,), fetch="one"
        )

    def update_password_hash(self, user_id, senha_hash):
        self._execute("UPDATE users SET senha_hash = ? WHERE id = ?", (senha_hash, user_id))

    # --- agendamentos -----------------------------------------------------
    def slot_taken(self, data_iso, hora, exclude_id=0):
        row = self._execute(
            "SELECT 1 FROM appointments WHERE data = ? AND hora = ? AND id != ?",
            (data_iso, hora, exclude_id),
            fetch="one",
        )
        return row is not None

    def add_appointment(self, user_id, data_iso, hora):
        return self._execute(
            "INSERT INTO appointments (user_id, data, hora, criado_em) VALUES (?, ?, ?, ?)",
            (user_id, data_iso, hora, datetime.now().isoformat()),
        )

    def get_appointment(self, appt_id):
        return self._execute(
            "SELECT id, user_id, data, hora FROM appointments WHERE id = ?",
            (appt_id,),
            fetch="one",
        )

    def get_appointments(self, user_id=None, search=None):
        query = (
            "SELECT a.id, u.nome, a.data, a.hora, a.criado_em"
            " FROM appointments a JOIN users u ON a.user_id = u.id"
        )
        clauses, params = [], []
        if user_id is not None:
            clauses.append("a.user_id = ?")
            params.append(user_id)
        if search:
            like = _like(search)
            clauses.append(
                "(u.nome LIKE ? ESCAPE '\\' OR a.data LIKE ? ESCAPE '\\'"
                " OR (substr(a.data, 9, 2) || '/' || substr(a.data, 6, 2) || '/' || substr(a.data, 1, 4))"
                " LIKE ? ESCAPE '\\')"
            )
            params.extend((like, like, like))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY a.data, a.hora"
        return self._execute(query, params, fetch="all")

    def update_appointment(self, appt_id, data_iso, hora):
        self._execute(
            "UPDATE appointments SET data = ?, hora = ? WHERE id = ?",
            (data_iso, hora, appt_id),
        )

    def delete_appointment(self, appt_id):
        self._execute("DELETE FROM appointments WHERE id = ?", (appt_id,))


# ----------------------------------------------------------------------------
# Formulário de agendamento (adicionar / editar)
# ----------------------------------------------------------------------------
class AppointmentForm(tk.Toplevel):
    def __init__(self, master, db, user_id, on_saved, appt=None):
        super().__init__(master)
        self.db, self.user_id, self.on_saved = db, user_id, on_saved
        self.appt_id = appt[0] if appt else None

        self.title("Editar agendamento" if appt else "Novo agendamento")
        self.resizable(False, False)
        self.transient(master)

        frame = ttk.Frame(self, padding=16)
        frame.pack()

        ttk.Label(frame, text="Data (DD/MM/AAAA)").pack(pady=(0, 2))
        self.date_entry = ttk.Entry(frame, width=22, justify="center")
        self.date_entry.pack(pady=(0, 8))

        ttk.Label(frame, text="Hora (HH:MM)").pack(pady=(0, 2))
        self.time_entry = ttk.Entry(frame, width=22, justify="center")
        self.time_entry.pack(pady=(0, 8))

        self.error_var = tk.StringVar()
        tk.Label(frame, textvariable=self.error_var, fg="#b00020", wraplength=220).pack()

        ttk.Button(frame, text="Confirmar", command=self._save).pack(pady=(8, 0))

        if appt:
            self.date_entry.insert(0, iso_to_br(appt[2]))
            self.time_entry.insert(0, appt[3])

        for entry in (self.date_entry, self.time_entry):
            entry.bind("<KeyRelease>", self._on_key)
        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

        self.date_entry.focus_set()
        self.grab_set()

    @staticmethod
    def _reformat(entry, formatter):
        current = entry.get()
        new = formatter(current)
        if current != new:
            entry.delete(0, tk.END)
            entry.insert(0, new)

    def _on_key(self, _event=None):
        self._reformat(self.date_entry, format_date_text)
        self._reformat(self.time_entry, format_time_text)
        self.error_var.set(
            validate_slot(self.date_entry.get(), self.time_entry.get(), partial=True) or ""
        )

    def _save(self):
        date_text = self.date_entry.get().strip()
        time_text = self.time_entry.get().strip()

        error = validate_slot(date_text, time_text)
        if error:
            self.error_var.set(error)
            return

        date_iso = parse_date(date_text).isoformat()
        if self.db.slot_taken(date_iso, time_text, exclude_id=self.appt_id or 0):
            self.error_var.set("Esse horário já está reservado.")
            return

        if self.appt_id:
            self.db.update_appointment(self.appt_id, date_iso, time_text)
        else:
            self.db.add_appointment(self.user_id, date_iso, time_text)

        self.on_saved()
        self.destroy()


# ----------------------------------------------------------------------------
# Janela de agendamentos
# ----------------------------------------------------------------------------
class AppointmentWindow(tk.Toplevel):
    TABS = ("Futuros", "Passados")
    COLUMNS = ("ID", "Nome", "Data", "Hora", "Criado em")
    WIDTHS = {"ID": 60, "Nome": 300, "Data": 130, "Hora": 100, "Criado em": 200}

    def __init__(self, master, db, user=None):
        super().__init__(master)
        self.db, self.user = db, user  # user=None -> visão do dono
        self.title(f"Agendamentos{' - ' + user[1] if user else ''}")
        self.geometry("1020x580")

        self.search_var = tk.StringVar()
        if not user:
            sf = ttk.Frame(self)
            sf.pack(fill=tk.X, pady=5, padx=5)
            ttk.Label(sf, text="Buscar (nome ou data):").pack(side=tk.LEFT)
            entry = ttk.Entry(sf, textvariable=self.search_var, width=30)
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind("<Return>", lambda _e: self.refresh())
            ttk.Button(sf, text="Pesquisar", command=self.refresh).pack(side=tk.LEFT)
            ttk.Button(sf, text="Limpar", command=self._clear_search).pack(side=tk.LEFT, padx=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", pady=5, padx=5)
        self.trees = {}
        for tab in self.TABS:
            frm = ttk.Frame(self.notebook)
            self.notebook.add(frm, text=tab)
            tv = ttk.Treeview(frm, columns=self.COLUMNS, show="headings", selectmode="browse")
            for col in self.COLUMNS:
                tv.heading(col, text=col)
                tv.column(col, anchor="center", width=self.WIDTHS[col])
            sb = ttk.Scrollbar(frm, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            tv.pack(expand=True, fill="both")
            self.trees[tab] = tv

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        if user:
            ttk.Button(btns, text="Adicionar", command=self.add).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Editar", command=self.edit).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Excluir", command=self.delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.refresh()

    def _clear_search(self):
        self.search_var.set("")
        self.refresh()

    def refresh(self):
        for tv in self.trees.values():
            tv.delete(*tv.get_children())

        term = self.search_var.get().strip() or None
        appts = self.db.get_appointments(
            user_id=self.user[0] if self.user else None, search=term
        )
        now = datetime.now()
        for appt_id, nome, data_iso, hora, criado in appts:
            when = datetime.strptime(f"{data_iso} {hora}", "%Y-%m-%d %H:%M")
            tab = "Futuros" if when >= now else "Passados"
            # Passados em ordem decrescente (mais recentes primeiro)
            position = 0 if tab == "Passados" else tk.END
            self.trees[tab].insert(
                "",
                position,
                iid=str(appt_id),
                values=(appt_id, nome, iso_to_br(data_iso), hora, format_created(criado)),
            )

    def _selected(self):
        """Retorna (aba, id) do item selecionado na aba atual, ou None."""
        tab = self.notebook.tab(self.notebook.select(), "text")
        selection = self.trees[tab].selection()
        if not selection:
            messagebox.showinfo("Atenção", "Selecione um agendamento.", parent=self)
            return None
        return tab, int(selection[0])

    def _own_appointment(self, appt_id):
        """Busca o agendamento garantindo que pertence ao usuário logado."""
        appt = self.db.get_appointment(appt_id)
        if not appt or appt[1] != self.user[0]:
            messagebox.showerror("Erro", "Agendamento não encontrado.", parent=self)
            self.refresh()
            return None
        return appt

    def add(self):
        AppointmentForm(self, self.db, self.user[0], self.refresh)

    def edit(self):
        selected = self._selected()
        if not selected:
            return
        tab, appt_id = selected
        if tab == "Passados":
            messagebox.showinfo("Atenção", "Agendamentos passados não podem ser editados.", parent=self)
            return
        appt = self._own_appointment(appt_id)
        if appt:
            AppointmentForm(self, self.db, self.user[0], self.refresh, appt=appt)

    def delete(self):
        selected = self._selected()
        if not selected:
            return
        _, appt_id = selected
        if not self._own_appointment(appt_id):
            return
        if messagebox.askyesno("Confirmar", "Excluir agendamento?", parent=self):
            self.db.delete_appointment(appt_id)
            self.refresh()


# ----------------------------------------------------------------------------
# Janela principal (Login e Cadastro)
# ----------------------------------------------------------------------------
class LoginApp(tk.Tk):
    W, H = 1020, 580
    PANEL_W, PANEL_H = 360, 320

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Sistema de Login e Cadastro")
        self.geometry(f"{self.W}x{self.H}")
        self.resizable(False, False)

        try:
            self.iconphoto(False, tk.PhotoImage(file="imagens/icon.png"))
        except tk.TclError:
            pass  # ícone é opcional

        self._build_ui()

    @staticmethod
    def _make_rounded_panel(w, h, radius=12, alpha=255, color=(240, 240, 240)):
        """Cria uma imagem RGBA com cantos arredondados para servir de painel."""
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=alpha)
        panel = Image.new("RGBA", (w, h), color + (0,))
        panel.putalpha(mask)
        return panel

    def _place(self, group, widget, x, y):
        group.append(self.canvas.create_window(x, y, window=widget))

    def _build_ui(self):
        try:
            bg = Image.open("imagens/background.png").convert("RGB")
        except (OSError, ValueError):
            bg = Image.new("RGB", (self.W, self.H), (50, 50, 50))

        self.canvas = tk.Canvas(self, width=self.W, height=self.H, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # referências guardadas em self para evitar coleta de lixo
        self._bg_photo = ImageTk.PhotoImage(bg.resize((self.W, self.H), Image.LANCZOS))
        self.canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)

        cx, cy = self.W // 2, self.H // 2
        panel = self._make_rounded_panel(self.PANEL_W, self.PANEL_H)
        self._panel_photo = ImageTk.PhotoImage(panel)
        self.canvas.create_image(cx, cy, image=self._panel_photo)

        # abas (botões) sobre o painel
        tab_y = cy - self.PANEL_H // 2 + 16
        self._tab_buttons = {
            "login": tk.Button(self, text="Login", relief="flat", command=lambda: self._show_tab("login")),
            "register": tk.Button(self, text="Cadastro", relief="flat", command=lambda: self._show_tab("register")),
        }
        self.canvas.create_window(cx - 60, tab_y, window=self._tab_buttons["login"])
        self.canvas.create_window(cx + 40, tab_y, window=self._tab_buttons["register"])

        self._login_items, self._reg_items = [], []
        self._build_login(cx, cy)
        self._build_register(cx, cy)
        self._show_tab("login")

    def _label(self, text):
        return tk.Label(self, text=text, bg=PANEL_BG)

    def _build_login(self, cx, cy):
        base_y = cy - 40
        self._login_entries = {
            "E-mail": tk.Entry(self, width=30),
            "Senha": tk.Entry(self, width=30, show="*"),
        }
        self._place(self._login_items, self._label("E-mail:"), cx, base_y - 40)
        self._place(self._login_items, self._login_entries["E-mail"], cx, base_y - 20)
        self._place(self._login_items, self._label("Senha:"), cx, base_y + 10)
        self._place(self._login_items, self._login_entries["Senha"], cx, base_y + 30)
        self._place(self._login_items, tk.Button(self, text="Login", width=12, command=self._do_login), cx, base_y + 90)

        for entry in self._login_entries.values():
            entry.bind("<Return>", lambda _e: self._do_login())

    def _build_register(self, cx, cy):
        # telefone: apenas dígitos, até 11 caracteres
        vcmd = (self.register(lambda p: p == "" or (p.isdigit() and len(p) <= 11)), "%P")

        r_base, spacing = cy - 60, 46
        fields = [
            ("Nome", "Nome:", {}),
            ("E-mail", "E-mail:", {}),
            ("Telefone", "Telefone:", {"validate": "key", "validatecommand": vcmd}),
            ("Senha", "Senha:", {"show": "*"}),
        ]
        self._reg_entries = {}
        for i, (key, text, opts) in enumerate(fields):
            entry = tk.Entry(self, width=30, **opts)
            self._reg_entries[key] = entry
            self._place(self._reg_items, self._label(text), cx, r_base - 4 + spacing * i)
            self._place(self._reg_items, entry, cx, r_base + 14 + spacing * i)
            entry.bind("<Return>", lambda _e: self._do_register())

        self._place(
            self._reg_items,
            tk.Button(self, text="Cadastrar", width=12, command=self._do_register),
            cx,
            r_base + spacing * 4 + 6,
        )

    def _show_tab(self, name):
        for id_ in self._login_items:
            self.canvas.itemconfigure(id_, state="normal" if name == "login" else "hidden")
        for id_ in self._reg_items:
            self.canvas.itemconfigure(id_, state="normal" if name == "register" else "hidden")
        for key, btn in self._tab_buttons.items():
            btn.config(relief="sunken" if key == name else "flat")
        first = self._login_entries["E-mail"] if name == "login" else self._reg_entries["Nome"]
        first.focus_set()

    # --- cadastro -----------------------------------------------------------
    def _do_register(self):
        e = self._reg_entries
        nome = e["Nome"].get().strip()
        email = e["E-mail"].get().strip().lower()
        tel = e["Telefone"].get().strip()
        pwd = e["Senha"].get()  # senha não sofre strip

        if not nome:
            return messagebox.showwarning("Erro", "Informe o nome.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return messagebox.showwarning("Erro", "Informe um e-mail válido.")
        if tel and len(tel) < 10:
            return messagebox.showwarning("Erro", "Telefone deve ter DDD + número (10 ou 11 dígitos).")
        if len(pwd) < MIN_PASSWORD_LEN:
            return messagebox.showwarning("Erro", f"A senha deve ter ao menos {MIN_PASSWORD_LEN} caracteres.")
        if email == OWNER_EMAIL.lower() or self.db.get_user_by_email(email):
            return messagebox.showwarning("Erro", "E-mail já cadastrado.")

        try:
            self.db.add_user(nome, email, tel, hash_password(pwd))
        except sqlite3.IntegrityError:
            return messagebox.showwarning("Erro", "E-mail já cadastrado.")

        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso.")
        for entry in e.values():
            entry.delete(0, tk.END)
        self._show_tab("login")
        self._login_entries["E-mail"].insert(0, email)
        self._login_entries["Senha"].focus_set()

    # --- login --------------------------------------------------------------
    def _do_login(self):
        email = self._login_entries["E-mail"].get().strip()
        pwd = self._login_entries["Senha"].get()
        if not email or not pwd:
            return messagebox.showwarning("Erro", "Preencha todos os campos.")

        if is_owner(email, pwd):
            AppointmentWindow(self, self.db)
        else:
            user = self.db.get_user_by_email(email)
            if user and verify_password(pwd, user[4]):
                if needs_rehash(user[4]):  # migra hashes antigos para PBKDF2
                    self.db.update_password_hash(user[0], hash_password(pwd))
                AppointmentWindow(self, self.db, user)
            else:
                messagebox.showerror("Erro", "E-mail ou senha incorretos.")

        self._login_entries["Senha"].delete(0, tk.END)


if __name__ == "__main__":
    LoginApp().mainloop()
