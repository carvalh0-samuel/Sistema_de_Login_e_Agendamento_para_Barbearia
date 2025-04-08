import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import re
import hashlib

ARQUIVO_USUARIOS = "usuarios.csv"
ARQUIVO_AGENDAMENTOS = "agendamentos.csv"

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Login e Cadastro")
        self.root.geometry("800x500")
        self.root.resizable(False, False)

        self.verificar_arquivos()
        self.criar_widgets()

    def verificar_arquivos(self):
        """Cria os arquivos CSV se não existirem."""
        if not os.path.exists(ARQUIVO_USUARIOS):
            with open(ARQUIVO_USUARIOS, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Nome", "Email", "Telefone", "Senha"])
        
        if not os.path.exists(ARQUIVO_AGENDAMENTOS):
            with open(ARQUIVO_AGENDAMENTOS, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Nome", "Data", "Hora"])

    def criar_widgets(self):
        """Cria os elementos da interface."""
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
        """Cria a interface de login."""
        ttk.Label(self.aba_login, text="E-mail:").pack(pady=15)
        self.entry_email_login = ttk.Entry(self.aba_login)
        self.entry_email_login.pack()

        ttk.Label(self.aba_login, text="Senha:").pack(pady=15)
        self.entry_senha_login = ttk.Entry(self.aba_login, show="*")
        self.entry_senha_login.pack()

        ttk.Button(self.aba_login, text="Entrar", command=self.login).pack(pady=10)

    def criar_tela_cadastro(self):
        """Cria a interface de cadastro."""
        ttk.Label(self.aba_cadastro, text="Nome:").pack(pady=15)
        self.entry_nome = ttk.Entry(self.aba_cadastro)
        self.entry_nome.pack()

        ttk.Label(self.aba_cadastro, text="E-mail:").pack(pady=15)
        self.entry_email = ttk.Entry(self.aba_cadastro)
        self.entry_email.pack()

        ttk.Label(self.aba_cadastro, text="Telefone:").pack(pady=15)
        
        # Validação para permitir apenas números e limitar a 11 caracteres
        self.valida_telefone = self.root.register(self.validar_telefone)
        self.entry_telefone = ttk.Entry(self.aba_cadastro, validate="key", validatecommand=(self.valida_telefone, "%P"))
        self.entry_telefone.pack()

        ttk.Label(self.aba_cadastro, text="Senha:").pack(pady=15)
        self.entry_senha = ttk.Entry(self.aba_cadastro, show="*")
        self.entry_senha.pack()

        ttk.Button(self.aba_cadastro, text="Cadastrar", command=self.cadastrar).pack(pady=10)

    def validar_telefone(self, novo_valor):
        """Permite apenas números e limita a 11 caracteres no campo telefone."""
        if novo_valor.isdigit() and len(novo_valor) <= 11:
            return True
        return False

    def validar_email(self, email):
        """Valida o formato de um e-mail."""
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return True
        return False

    def hash_senha(self, senha):
        """Cria um hash SHA-256 para a senha."""
        return hashlib.sha256(senha.encode('utf-8')).hexdigest()

    def verificar_senha(self, senha_digitada, senha_armazenada):
        """Compara a senha digitada com a senha armazenada (em hash)."""
        return self.hash_senha(senha_digitada) == senha_armazenada

    def cadastrar(self):
        """Função para cadastrar um novo usuário."""
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

        if any(user[1] == email for user in usuarios):  # Verifica se o e-mail já está cadastrado
            messagebox.showwarning("Erro", "E-mail já cadastrado!")
            return

        senha_hash = self.hash_senha(senha)
        self.salvar_usuario(nome, email, telefone, senha_hash)
        messagebox.showinfo("Sucesso", "Cadastro realizado com sucesso!")
        self.limpar_campos()

    def login(self):
        """Função para validar login."""
        email = self.entry_email_login.get().strip()
        senha = self.entry_senha_login.get().strip()

        if not email or not senha:
            messagebox.showwarning("Erro", "Preencha todos os campos!")
            return

        usuarios = self.carregar_usuarios()

        if any(user[1] == email and self.verificar_senha(senha, user[3]) for user in usuarios):  # Verifica o login
            nome = next(user[0] for user in usuarios if user[1] == email)
            messagebox.showinfo("Sucesso", f"Bem-vindo, {nome}!")
            self.abrir_agendamento(nome)  # Abre a janela de agendamento após o login bem-sucedido
        else:
            messagebox.showerror("Erro", "E-mail ou senha incorretos!")

    def carregar_usuarios(self):
        """Carrega todos os usuários do arquivo CSV."""
        try:
            with open(ARQUIVO_USUARIOS, "r") as file:
                reader = csv.reader(file)
                next(reader)  # Ignora o cabeçalho
                return [linha for linha in reader]
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar usuários: {str(e)}")
            return []

    def salvar_usuario(self, nome, email, telefone, senha):
        """Salva um novo usuário no arquivo CSV.""" 
        with open(ARQUIVO_USUARIOS, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([nome, email, telefone, senha])

    def limpar_campos(self):
        """Limpa os campos de entrada após cadastro.""" 
        self.entry_nome.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_telefone.delete(0, tk.END)
        self.entry_senha.delete(0, tk.END)

    def abrir_agendamento(self, nome_usuario):
        """Cria a janela de agendamento após o login.""" 
        agendamento_window = tk.Toplevel(self.root)
        agendamento_window.title(f"Agendamento - {nome_usuario}")
        agendamento_window.geometry("400x300")
        
        ttk.Label(agendamento_window, text="Escolha a data e horário:").pack(pady=20)
        
        ttk.Label(agendamento_window, text="Data (DD/MM/AAAA):").pack(pady=5)
        entry_data = ttk.Entry(agendamento_window)
        entry_data.pack(pady=5)
        
        # Adicionando a formatação automática de data
        entry_data.bind("<KeyRelease>", lambda event: self.formatar_data(entry_data))

        ttk.Label(agendamento_window, text="Hora (HH:MM):").pack(pady=5)
        entry_hora = ttk.Entry(agendamento_window)
        entry_hora.pack(pady=5)
        
        # Adicionando a formatação automática de hora
        entry_hora.bind("<KeyRelease>", lambda event: self.formatar_hora(entry_hora))

        ttk.Button(agendamento_window, text="Agendar", command=lambda: self.confirmar_agendamento(entry_data.get(), entry_hora.get(), nome_usuario)).pack(pady=20)

    def formatar_data(self, entry_data):
        """Formata automaticamente a data enquanto o usuário digita e limita o número de caracteres."""
        data = entry_data.get().replace("/", "")  # Remove qualquer barra existente
        if len(data) > 10:  # Limita a 10 caracteres (DD/MM/AAAA)
            data = data[:10]
        if len(data) > 2:
            data = data[:2] + "/" + data[2:]  # Adiciona a barra após o dia
        if len(data) > 5:
            data = data[:5] + "/" + data[5:]  # Adiciona a barra após o mês
        entry_data.delete(0, tk.END)  # Limpa o campo de entrada
        entry_data.insert(0, data)  # Insere a data formatada

    def formatar_hora(self, entry_hora):
        """Formata automaticamente a hora enquanto o usuário digita e limita o número de caracteres."""
        hora = entry_hora.get().replace(":", "")  # Remove qualquer dois-pontos existente
        if len(hora) > 5:  # Limita a 5 caracteres (HH:MM)
            hora = hora[:5]
        if len(hora) > 2:
            hora = hora[:2] + ":" + hora[2:]  # Adiciona o dois-pontos após a hora
        entry_hora.delete(0, tk.END)  # Limpa o campo de entrada
        entry_hora.insert(0, hora)  # Insere a hora formatada

    def confirmar_agendamento(self, data, hora, nome_usuario):
        """Confirma o agendamento e exibe uma mensagem.""" 
        if not data or not hora:
            messagebox.showwarning("Erro", "Preencha todos os campos de data e hora!")
            return
        
        if not self.validar_data(data):
            messagebox.showwarning("Erro", "Data inválida! Use o formato DD/MM/AAAA.")
            return
        
        if not self.validar_hora(hora):
            messagebox.showwarning("Erro", "Hora inválida! Use o formato HH:MM.")
            return
        
        # Salva o agendamento no arquivo CSV
        self.salvar_agendamento(nome_usuario, data, hora)

        messagebox.showinfo("Sucesso", f"Agendamento realizado com sucesso!\nData: {data}\nHora: {hora}\nUsuário: {nome_usuario}")

    def salvar_agendamento(self, nome, data, hora):
        """Salva o agendamento no arquivo CSV."""
        with open(ARQUIVO_AGENDAMENTOS, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([nome, data, hora])

# Executando a aplicação
if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()
