import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import re
import hashlib
from datetime import datetime

ARQUIVO_USUARIOS = "usuarios.csv"
ARQUIVO_AGENDAMENTOS = "agendamentos.csv"

# Defina o e-mail e senha do dono
EMAIL_DONO = "donobarber@example.com"
SENHA_DONO_HASH = hashlib.sha256("senha_do_dono".encode('utf-8')).hexdigest()

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Login e Cadastro")
        self.root.geometry("800x500")
        self.root.resizable(False, False)

        self.verificar_arquivos()
        self.criar_widgets()

    def verificar_arquivos(self):
        if not os.path.exists(ARQUIVO_USUARIOS):
            with open(ARQUIVO_USUARIOS, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Nome", "Email", "Telefone", "Senha"])
        
        if not os.path.exists(ARQUIVO_AGENDAMENTOS):
            with open(ARQUIVO_AGENDAMENTOS, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Nome", "Data", "Hora"])

    def criar_widgets(self):
        self.frame = ttk.Frame(self.root)
        self.frame.pack(pady=70)

        self.abas = ttk.Notebook(self.frame)
        self.aba_login = ttk.Frame(self.abas)
        self.aba_cadastro = ttk.Frame(self.abas)

        self.abas.add(self.aba_login, text="Login")
        self.abas.add(self.aba_cadastro, text="Cadastro")
        self.abas.pack(expand=True, fill="both")

        self.criar_tela_login()
        self.criar_tela_cadastro()

    def criar_tela_login(self):
        ttk.Label(self.aba_login, text="E-mail:").pack(pady=15)
        self.entry_email_login = ttk.Entry(self.aba_login)
        self.entry_email_login.pack()

        ttk.Label(self.aba_login, text="Senha:").pack(pady=15)
        self.entry_senha_login = ttk.Entry(self.aba_login, show="*")
        self.entry_senha_login.pack()

        ttk.Button(self.aba_login, text="Entrar", command=self.login).pack(pady=10)

    def criar_tela_cadastro(self):
        ttk.Label(self.aba_cadastro, text="Nome:").pack(pady=15)
        self.entry_nome = ttk.Entry(self.aba_cadastro)
        self.entry_nome.pack()

        ttk.Label(self.aba_cadastro, text="E-mail:").pack(pady=15)
        self.entry_email = ttk.Entry(self.aba_cadastro)
        self.entry_email.pack()

        ttk.Label(self.aba_cadastro, text="Telefone:").pack(pady=15)
        self.valida_telefone = self.root.register(self.validar_telefone)
        self.entry_telefone = ttk.Entry(self.aba_cadastro, validate="key", validatecommand=(self.valida_telefone, "%P"))
        self.entry_telefone.pack()

        ttk.Label(self.aba_cadastro, text="Senha:").pack(pady=15)
        self.entry_senha = ttk.Entry(self.aba_cadastro, show="*")
        self.entry_senha.pack()

        ttk.Button(self.aba_cadastro, text="Cadastrar", command=self.cadastrar).pack(pady=10)

    def validar_telefone(self, novo_valor):
        return novo_valor.isdigit() and len(novo_valor) <= 11

    def validar_email(self, email):
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

    def hash_senha(self, senha):
        return hashlib.sha256(senha.encode('utf-8')).hexdigest()

    def verificar_senha(self, senha_digitada, senha_armazenada):
        return self.hash_senha(senha_digitada) == senha_armazenada

    def cadastrar(self):
        nome = self.entry_nome.get().strip()
        email = self.entry_email.get().strip()
        telefone = self.entry_telefone.get().strip()
        senha = self.entry_senha.get().strip()

        if not nome or not email or not telefone or not senha:
            messagebox.showwarning("Erro", "Todos os campos devem ser preenchidos!")
            return
        
        if not self.validar_email(email):
            messagebox.showwarning("Erro", "E-mail inválido!")
            return

        usuarios = self.carregar_usuarios()

        if any(user[1] == email for user in usuarios):
            messagebox.showwarning("Erro", "E-mail já cadastrado!")
            return

        senha_hash = self.hash_senha(senha)
        self.salvar_usuario(nome, email, telefone, senha_hash)
        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso!")
        self.limpar_campos()

    def login(self):
        email = self.entry_email_login.get().strip()
        senha = self.entry_senha_login.get().strip()

        if not email or not senha:
            messagebox.showwarning("Erro", "Preencha todos os campos!")
            return

        usuarios = self.carregar_usuarios()

        # Verifica se o usuário é o dono
        if email == EMAIL_DONO and self.verificar_senha(senha, SENHA_DONO_HASH):
            messagebox.showinfo("Sucesso", "Bem-vindo, Dono da Barbearia!")
            self.abrir_agendamento_admin()
        # Verifica se o e-mail e a senha correspondem a um usuário cadastrado
        elif any(user[1] == email and self.verificar_senha(senha, user[3]) for user in usuarios):
            nome = next(user[0] for user in usuarios if user[1] == email)
            messagebox.showinfo("Sucesso", f"Bem-vindo, {nome}!")
            self.abrir_agendamento(nome)
        else:
            messagebox.showerror("Erro", "E-mail ou senha incorretos!")

    def carregar_usuarios(self):
        try:
            with open(ARQUIVO_USUARIOS, "r") as file:
                reader = csv.reader(file)
                next(reader)
                return [linha for linha in reader]
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar usuários: {str(e)}")
            return []

    def salvar_usuario(self, nome, email, telefone, senha):
        with open(ARQUIVO_USUARIOS, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([nome, email, telefone, senha])

    def limpar_campos(self):
        self.entry_nome.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_telefone.delete(0, tk.END)
        self.entry_senha.delete(0, tk.END)

    def abrir_agendamento(self, nome_usuario):
        agendamento_window = tk.Toplevel(self.root)
        agendamento_window.title(f"Agendamentos - {nome_usuario}")
        agendamento_window.geometry("400x300")
        
        ttk.Label(agendamento_window, text="Escolha a data e horário:").pack(pady=20)
        
        ttk.Label(agendamento_window, text="Data (DD/MM/AAAA):").pack(pady=5)
        entry_data = ttk.Entry(agendamento_window)
        entry_data.pack(pady=5)
        entry_data.bind("<KeyRelease>", lambda event: self.formatar_data(entry_data))

        ttk.Label(agendamento_window, text="Hora (HH:MM):").pack(pady=5)
        entry_hora = ttk.Entry(agendamento_window)
        entry_hora.pack(pady=5)
        entry_hora.bind("<KeyRelease>", lambda event: self.formatar_hora(entry_hora))

        ttk.Button(agendamento_window, text="Agendar", command=lambda: self.confirmar_agendamento(entry_data.get(), entry_hora.get(), nome_usuario)).pack(pady=20)

    def formatar_data(self, entry_data):
        data = entry_data.get().replace("/", "")
        if len(data) > 8:  # Limita a 8 caracteres (DD/MM/AAAA)
            data = data[:8]
        if len(data) > 2:
            data = data[:2] + "/" + data[2:]
        if len(data) > 5:
            data = data[:5] + "/" + data[5:]
        entry_data.delete(0, tk.END)
        entry_data.insert(0, data)

    def formatar_hora(self, entry_hora):
        hora = entry_hora.get().replace(":", "")
        if len(hora) > 4:  # Limita a 4 caracteres (HH:MM)
            hora = hora[:4]
        if len(hora) > 2:
            hora = hora[:2] + ":" + hora[2:]
        entry_hora.delete(0, tk.END)
        entry_hora.insert(0, hora)

    def validar_data(self, data_str):
        try:
            data = datetime.strptime(data_str, "%d/%m/%Y")
            if data.date() < datetime.today().date():
                return False
            return True
        except ValueError:
            return False

    def validar_hora(self, hora_str):
        try:
            datetime.strptime(hora_str, "%H:%M")
            return True
        except ValueError:
            return False

    def confirmar_agendamento(self, data, hora, nome_usuario):
        if not data or not hora:
            messagebox.showwarning("Erro", "Preencha todos os campos de data e hora!")
            return
        
        if not self.validar_data(data):
            messagebox.showwarning("Erro", "Data inválida! Use o formato DD/MM/AAAA e escolha uma data futura.")
            return
        
        if not self.validar_hora(hora):
            messagebox.showwarning("Erro", "Hora inválida! Use o formato HH:MM.")
            return
        
        self.salvar_agendamento(nome_usuario, data, hora)
        messagebox.showinfo("Sucesso", f"Agendamento realizado!\nData: {data}\nHora: {hora}")

    def salvar_agendamento(self, nome, data, hora):
        with open(ARQUIVO_AGENDAMENTOS, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([nome, data, hora])

    def abrir_agendamento_admin(self):
        # Somente o dono pode ver todos os agendamentos
        self.visualizar_agendamentos()

    def visualizar_agendamentos(self):
        # Abre uma janela para o dono visualizar todos os agendamentos
        janela_agendamentos = tk.Toplevel(self.root)
        janela_agendamentos.title("Agendamentos Realizados")
        janela_agendamentos.geometry("600x400")

        agendamentos = self.carregar_agendamentos()

        ttk.Label(janela_agendamentos, text="Agendamentos Realizados", font=("Arial", 16)).pack(pady=10)

        tree = ttk.Treeview(janela_agendamentos, columns=("Nome", "Data", "Hora"), show="headings")
        tree.heading("Nome", text="Nome")
        tree.heading("Data", text="Data")
        tree.heading("Hora", text="Hora")
        tree.pack(expand=True, fill="both")

        for agendamento in agendamentos:
            tree.insert("", tk.END, values=agendamento)

        ttk.Button(janela_agendamentos, text="Fechar", command=janela_agendamentos.destroy).pack(pady=10)

    def carregar_agendamentos(self):
        try:
            with open(ARQUIVO_AGENDAMENTOS, "r") as file:
                reader = csv.reader(file)
                next(reader)
                return [linha for linha in reader]
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar agendamentos: {str(e)}")
            return []

# Executando a aplicação
if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()
