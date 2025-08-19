import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import sqlite3
import re
import hashlib
from datetime import datetime, date

# Arquivo do banco de dados
DB_FILE = "app.db"
# Credenciais fixas do dono do sistema
EMAIL_DONO = "sam@s.com"
SENHA_DONO_HASH = hashlib.sha256("12345".encode()).hexdigest()

# Função para gerar hash da senha
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# Classe para manipulação do banco de dados
class Database:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._initialize()  # Cria tabelas caso não existam

    def _initialize(self):
        # Criação das tabelas: usuários e agendamentos
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

    # Adiciona novo usuário
    def add_user(self, nome, email, telefone, senha_hash):
        criado = datetime.now().isoformat()
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO users (nome, email, telefone, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
                (nome, email, telefone, senha_hash, criado)
            )

    # Busca usuário pelo e-mail
    def get_user_by_email(self, email):
        with sqlite3.connect(self.db_file) as conn:
            return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    # Adiciona agendamento
    def add_appointment(self, user_id, data, hora):
        criado = datetime.now().isoformat()
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO appointments (user_id, data, hora, criado_em) VALUES (?, ?, ?, ?)",
                (user_id, data, hora, criado)
            )

    # Retorna agendamentos (com filtros opcionais por usuário e busca)
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
        # Ordena por data e hora
        query += (
            " ORDER BY substr(a.data, 7, 4) || '-' || substr(a.data, 4, 2) || '-' || substr(a.data, 1, 2), a.hora"
        )
        with sqlite3.connect(self.db_file) as conn:
            return conn.execute(query, params).fetchall()

    # Atualiza agendamento
    def update_appointment(self, appt_id, data, hora):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "UPDATE appointments SET data = ?, hora = ? WHERE id = ?",
                (data, hora, appt_id)
            )

    # Deleta agendamento
    def delete_appointment(self, appt_id):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))


# Classe para validações de data e hora
class Validator:
    @staticmethod
    def _validate_date(entry, show=True):
        # Formata a entrada de data automaticamente
        txt = entry.get().replace('/', '')[:8]
        if len(txt) > 2: txt = f"{txt[:2]}/{txt[2:]}"
        if len(txt) > 5: txt = f"{txt[:5]}/{txt[5:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)

        # Só valida se estiver completo
        if len(txt) < 10: return True
        try:
            date_obj = datetime.strptime(txt, "%d/%m/%Y").date()
            # Data não pode ser no passado
            if date_obj < date.today(): raise ValueError
            return True
        except ValueError:
            if show: messagebox.showwarning("Erro", "Data inválida ou no passado.")
            return False

    @staticmethod
    def _validate_time(entry, show=True):
        # Formata a entrada de hora automaticamente
        txt = entry.get().replace(':', '')[:4]
        if len(txt) > 2: txt = f"{txt[:2]}:{txt[2:]}"
        entry.delete(0, tk.END); entry.insert(0, txt)

        # Só valida se estiver completo
        if len(txt) < 5: return True
        try:
            input_time = datetime.strptime(txt, "%H:%M").time()
            # Obtém a data associada para checar se é no mesmo dia
            parent = entry.master; date_entry = None
            for child in parent.winfo_children():
                if isinstance(child, ttk.Entry) and child != entry:
                    date_entry = child; break
            if date_entry:
                input_date = datetime.strptime(date_entry.get(), "%d/%m/%Y").date()
                # Se for hoje, hora não pode ser no passado
                if input_date == date.today() and input_time <= datetime.now().time():
                    raise ValueError
            return True
        except Exception:
            if show: messagebox.showwarning("Erro", "Hora inválida ou no passado.")
            return False


# Janela de agendamentos
class AppointmentWindow(tk.Toplevel):
    def __init__(self, master, db, user=None):
        super().__init__(master)
        self.db = db; self.user = user
        self.title(f"Agendamentos{' - ' + user[1] if user else ''}")
        self.geometry("1020x580")

        # Campo de busca aparece apenas para o dono
        if not user:
            sf = ttk.Frame(self); sf.pack(fill=tk.X, pady=5, padx=5)
            tk.Label(sf, text="Buscar:").pack(side=tk.LEFT)
            self.search_var = tk.StringVar()
            tk.Entry(sf, textvariable=self.search_var).pack(side=tk.LEFT, padx=5)
            ttk.Button(sf, text="Pesquisar", command=self.refresh).pack(side=tk.LEFT)

        # Abas internas: Futuros / Passados
        inner_nb = ttk.Notebook(self); inner_nb.pack(expand=True, fill='both', pady=5, padx=5)
        self.frames = {}
        for tab in ("Futuros", "Passados"):
            frm = ttk.Frame(inner_nb); inner_nb.add(frm, text=tab)
            # Tabela de agendamentos
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
        # Limpa todas as tabelas
        for tv in self.frames.values():
            for iid in tv.get_children(): tv.delete(iid)
        # Busca registros do banco
        term = self.search_var.get().strip() if hasattr(self, 'search_var') else None
        appts = self.db.get_appointments(user_id=(self.user[0] if self.user else None), search=term)
        # Classifica em futuros ou passados
        for a in appts:
            appt_date = datetime.strptime(a[2], "%d/%m/%Y").date()
            tab = "Futuros" if appt_date >= date.today() else "Passados"
            self.frames[tab].insert("", tk.END, values=a)

    # Abre formulário para adicionar agendamento
    def add(self): self._open_form('add')
    # Abre formulário para editar agendamento selecionado
    def edit(self):
        for tv in self.frames.values():
            sel = tv.focus()
            if sel:
                vals = tv.item(sel, 'values')
                return self._open_form('edit', vals)
    # Exclui agendamento selecionado
    def delete(self):
        for tv in self.frames.values():
            sel = tv.focus()
            if sel and messagebox.askyesno("Confirmar", "Excluir agendamento?", parent=self):
                self.db.delete_appointment(tv.item(sel)['values'][0])
                return self.refresh()

    # Formulário de agendamento (inclusão/edição)
    def _open_form(self, mode, appt=None):
        form = tk.Toplevel(self); form.title("Agendamento")
        entries = {}
        # Campos: Data e Hora
        for label, validator in [('Data (DD/MM/AAAA)', Validator._validate_date), ('Hora (HH:MM)', Validator._validate_time)]:
            ttk.Label(form, text=label).pack(pady=2)
            e = ttk.Entry(form); e.pack(pady=2)
            e.bind('<KeyRelease>', lambda ev, e=e, v=validator: v(e))
            entries[label] = e
        if appt:
            entries['Data (DD/MM/AAAA)'].insert(0, appt[2])
            entries['Hora (HH:MM)'].insert(0, appt[3])

        # Botão confirmar
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


# Janela principal (Login e Cadastro)
class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Sistema de Login e Cadastro")
        self.geometry("1020x580")
        self.resizable(False, False)

        # Tenta carregar ícone (se existir)
        try:
            self.iconphoto(False, tk.PhotoImage(file="imagens/icon.png"))
        except:
            pass

        # substituímos o Label de background por um Canvas na UI (feito no _build_ui)
        self._build_ui()

    def _make_rounded_panel(self, w, h, radius=12, alpha=200, color=(240,240,240)):
        """Cria imagem RGBA com cantos arredondados para servir de painel semi-transparente."""
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle((0,0,w,h), radius=radius, fill=alpha)
        color_layer = Image.new("RGBA", (w, h), color + (0,))
        color_layer.putalpha(mask)
        return color_layer

    def _build_ui(self):
        # tenta carregar o background; se falhar cria um background neutro
        try:
            self._orig_bg = Image.open("imagens/background.png").convert("RGB")
        except Exception:
            self._orig_bg = Image.new("RGB", (1020, 580), (50, 50, 50))

        # Canvas que conterá o fundo e os widgets
        w, h = 1020, 580
        self.canvas = tk.Canvas(self, width=w, height=h, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        # imagem de fundo (referência guardada em self para evitar GC)
        self._bg_photo = ImageTk.PhotoImage(self._orig_bg.resize((w, h), Image.LANCZOS))
        self._bg_id = self.canvas.create_image(0, 0, anchor='nw', image=self._bg_photo)

        # painel semi-transparente (card) no centro
        panel_w, panel_h = 360, 320
        overlay = self._make_rounded_panel(panel_w, panel_h, radius=12, alpha=220, color=(240,240,240))
        self._overlay_photo = ImageTk.PhotoImage(overlay)
        cx, cy = w // 2, h // 2
        self._panel_id = self.canvas.create_image(cx, cy, image=self._overlay_photo)

        # abas simples (botões) - posicionados sobre o painel
        b_login = tk.Button(self, text="Login", relief="flat", command=lambda: self._show_tab("login"))
        b_register = tk.Button(self, text="Cadastro", relief="flat", command=lambda: self._show_tab("register"))
        self._tab_login_id = self.canvas.create_window(cx - 60, cy - panel_h//2 + 16, window=b_login)
        self._tab_register_id = self.canvas.create_window(cx + 40, cy - panel_h//2 + 16, window=b_register)

        # --- Widgets de Login ---
        entries_login = {}
        lbl_e = tk.Label(self, text="E-mail:")
        ent_e = tk.Entry(self, width=30)
        lbl_s = tk.Label(self, text="Senha:")
        ent_s = tk.Entry(self, width=30, show="*")
        btn_login = tk.Button(self, text="Login", width=12, command=lambda e=entries_login: self._do_login(e))

        # posicionamento (coord relativas ao centro do painel)
        base_y = cy - 40
        self._login_ids = {
            "lbl_e": self.canvas.create_window(cx, base_y - 40, window=lbl_e),
            "ent_e": self.canvas.create_window(cx, base_y - 20, window=ent_e),
            "lbl_s": self.canvas.create_window(cx, base_y + 10, window=lbl_s),
            "ent_s": self.canvas.create_window(cx, base_y + 30, window=ent_s),
            "btn": self.canvas.create_window(cx, base_y + 90, window=btn_login)
        }
        entries_login["E-mail"] = ent_e
        entries_login["Senha"] = ent_s
        self._entries_login = entries_login

        # --- limitar caracteres de telefone ---
        vcmd = (self.register(lambda P: P.isdigit() and len(P) <= 11 or P == ""), "%P")

        # --- Widgets de Cadastro ---
        entries_reg = {}
        spacing = 46
        r_base = cy - 60
        lbl_nome = tk.Label(self, text="Nome:")
        ent_nome = tk.Entry(self, width=30)
        lbl_email = tk.Label(self, text="E-mail:")
        ent_email = tk.Entry(self, width=30)
        lbl_tel = tk.Label(self, text="Telefone:")
        ent_tel = tk.Entry(self, width=30, validate="key", validatecommand=vcmd)
        lbl_pwd = tk.Label(self, text="Senha:")
        ent_pwd = tk.Entry(self, width=30, show="*")
        btn_reg = tk.Button(self, text="Cadastrar", width=12, command=lambda e=entries_reg: self._do_register(e))

        self._reg_ids = {
            "lbl_nome": self.canvas.create_window(cx, r_base - 4, window=lbl_nome),
            "ent_nome": self.canvas.create_window(cx, r_base + 14, window=ent_nome),
            "lbl_email": self.canvas.create_window(cx, r_base + spacing, window=lbl_email),
            "ent_email": self.canvas.create_window(cx, r_base + spacing + 14, window=ent_email),
            "lbl_tel": self.canvas.create_window(cx, r_base + spacing*2, window=lbl_tel),
            "ent_tel": self.canvas.create_window(cx, r_base + spacing*2 + 14, window=ent_tel),
            "lbl_pwd": self.canvas.create_window(cx, r_base + spacing*3, window=lbl_pwd),
            "ent_pwd": self.canvas.create_window(cx, r_base + spacing*3 + 14, window=ent_pwd),
            "btn": self.canvas.create_window(cx, r_base + spacing*4 + 6, window=btn_reg)
        }
        entries_reg["Nome"] = ent_nome
        entries_reg["E-mail"] = ent_email
        entries_reg["Telefone"] = ent_tel
        entries_reg["Senha"] = ent_pwd
        self._entries_reg = entries_reg

        # mostra login por padrão
        self._show_tab("login")

    def _show_tab(self, name):
        # mostra/oculta widgets de login e registro
        for k, id_ in self._login_ids.items():
            self.canvas.itemconfigure(id_, state="normal" if name == "login" else "hidden")
        for k, id_ in self._reg_ids.items():
            self.canvas.itemconfigure(id_, state="normal" if name == "register" else "hidden")

    # Cadastro de novo usuário
    def _do_register(self, entries):
        nome = entries['Nome'].get().strip()
        email = entries['E-mail'].get().strip()
        tel = entries['Telefone'].get().strip()
        pwd = entries['Senha'].get().strip()
        # Validações básicas
        if not nome or not re.match(r"[^@]+@[^@]+\.[^@]+", email) or not pwd:
            return messagebox.showwarning("Erro", "Preencha corretamente todos os campos.")
        if self.db.get_user_by_email(email):
            return messagebox.showwarning("Erro", "E-mail já cadastrado.")
        self.db.add_user(nome, email, tel, hash_password(pwd))
        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso.")
        for e in entries.values():
            e.delete(0, tk.END)

    # Login de usuário ou dono
    def _do_login(self, entries):
        email = entries['E-mail'].get().strip()
        pwd = entries['Senha'].get().strip()
        if not email or not pwd:
            return messagebox.showwarning("Erro", "Preencha todos os campos.")
        # Login do dono
        if email == EMAIL_DONO and hash_password(pwd) == SENHA_DONO_HASH:
            AppointmentWindow(self, self.db)
        else:
            # Login de usuário cadastrado
            user = self.db.get_user_by_email(email)
            if user and hash_password(pwd) == user[4]:
                AppointmentWindow(self, self.db, user)
            else:
                messagebox.showerror("Erro", "E-mail ou senha incorretos.")


# Inicializa a aplicação
if __name__ == "__main__":
    LoginApp().mainloop()
