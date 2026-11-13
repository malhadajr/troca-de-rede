"""Interruptor de rede: widget que alterna entre Wi-Fi e Ethernet (Windows).

Para um lado, habilita o Wi-Fi e desabilita a Ethernet; para o outro, o inverso.
Clique para trocar, arraste para mover, botão direito para opções.
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import tkinter as tk

FUNDO, TRILHO, TEXTO, APAGADO = "#15171c", "#2b2f38", "#f2f4f7", "#5d6470"
COR = {"wifi": "#3b82f6", "ethernet": "#22c55e"}
ROTULO = {"wifi": "Wi-Fi", "ethernet": "Ethernet"}
POSICAO = {"wifi": 0.0, None: 0.5, "ethernet": 1.0}
LARG, ALT = 300, 96
CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "troca_rede.json")
TAREFA = "InterruptorDeRede"


def ps(comando):
    """Executa um comando PowerShell sem abrir janela e devolve a saída."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
         "$ErrorActionPreference='Stop';" + comando],
        capture_output=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if r.returncode:
        raise RuntimeError((r.stderr.strip().splitlines() or ["Falha no PowerShell"])[0])
    return r.stdout


def aspas(texto):
    return "'" + texto.replace("'", "''") + "'"


# ---------- rede ----------
def adaptadores():
    """Detecta os adaptadores físicos: {'wifi': (nome, habilitado), 'ethernet': (...)}."""
    saida = ps("Get-NetAdapter -Physical | ForEach-Object "
               "{ $_.PhysicalMediaType + '|' + $_.Status + '|' + $_.Name }")
    achados = {}
    for linha in saida.splitlines():
        midia, _, resto = linha.partition("|")
        status, _, nome = resto.partition("|")
        tipo = "wifi" if "802.11" in midia else "ethernet" if midia == "802.3" else None
        if tipo and nome:
            achados.setdefault(tipo, (nome.strip(), status != "Disabled"))
    return achados


def estado(ads):
    """'wifi' ou 'ethernet' se só um estiver habilitado; None se indefinido."""
    ligados = [t for t in ("wifi", "ethernet") if ads.get(t, ("", False))[1]]
    return ligados[0] if len(ligados) == 1 else None


def trocar_para(destino, ads):
    """Habilita o adaptador de destino e desabilita o outro."""
    outro = "ethernet" if destino == "wifi" else "wifi"
    ps(f"Enable-NetAdapter -Name {aspas(ads[destino][0])} -Confirm:$false;"
       f"Disable-NetAdapter -Name {aspas(ads[outro][0])} -Confirm:$false")


# ---------- iniciar com o Windows (tarefa agendada, sem pedir UAC a cada logon) ----------
def inicia_com_windows():
    return os.path.exists(os.path.join(os.environ["SystemRoot"], "System32", "Tasks", TAREFA))


def definir_inicio(ligar):
    if not ligar:
        ps(f"Unregister-ScheduledTask -TaskName '{TAREFA}' -Confirm:$false")
        return
    pasta, exe = os.path.split(sys.executable)
    if exe.lower() == "python.exe":
        exe = "pythonw.exe"
    ps("$u = $env:USERDOMAIN + '\\' + $env:USERNAME;"
       f"$a = New-ScheduledTaskAction -Execute {aspas(os.path.join(pasta, exe))}"
       f" -Argument ([char]34 + {aspas(os.path.abspath(sys.argv[0]))} + [char]34);"
       "$t = New-ScheduledTaskTrigger -AtLogOn -User $u;"
       "$p = New-ScheduledTaskPrincipal -UserId $u -RunLevel Highest;"
       "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries"
       " -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero);"
       f"Register-ScheduledTask -TaskName '{TAREFA}' -Action $a -Trigger $t"
       " -Principal $p -Settings $s -Force | Out-Null")


# ---------- widget ----------
class Interruptor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)  # sem moldura nem botão na barra de tarefas
        self.configure(bg=FUNDO)
        self.k = self.winfo_fpixels("1i") / 96  # escala de DPI
        self.ads, self.lado, self.pos, self.ocupado = {}, None, 0.5, True
        self.resultado, self.arrasto = None, None

        try:
            with open(CONFIG, encoding="utf-8") as f:
                self.cfg = json.load(f)
        except (OSError, ValueError):
            self.cfg = {}
        larg, alt = self.e(LARG), self.e(ALT)
        x = self.cfg.get("x", self.winfo_screenwidth() - larg - self.e(24))
        y = self.cfg.get("y", self.winfo_screenheight() - alt - self.e(72))
        x = max(0, min(x, self.winfo_screenwidth() - larg))
        y = max(0, min(y, self.winfo_screenheight() - alt))
        self.geometry(f"{larg}x{alt}+{x}+{y}")
        self.attributes("-topmost", self.cfg.get("topo", False))

        self.tela = tk.Canvas(self, width=larg, height=alt, bg=FUNDO,
                              highlightthickness=0, cursor="hand2")
        self.tela.pack()
        self.tela.bind("<Button-1>", self.pressionar)
        self.tela.bind("<B1-Motion>", self.arrastar)
        self.tela.bind("<ButtonRelease-1>", self.soltar)
        self.tela.bind("<Button-3>", self.menu)
        self.bind("<space>", self.clique)
        self.bind("<Escape>", lambda _: self.destroy())

        self.update_idletasks()
        try:  # cantos arredondados no Windows 11
            hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:
            pass

        self.msg = "Lendo adaptadores…"
        self.desenhar()
        self.em_segundo_plano(lambda: None)

    def e(self, v):
        return int(v * self.k)

    def salvar(self):
        self.update_idletasks()  # garante a posição já atualizada
        self.cfg.update(x=self.winfo_x(), y=self.winfo_y())
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f)
        except OSError:
            pass

    # ---------- desenho ----------
    def desenhar(self):
        t, e = self.tela, self.e
        t.delete("all")
        cx, cy, larg, alt = e(LARG / 2), e(40), e(72), e(34)
        x0, x1 = cx - (larg - alt) // 2, cx + (larg - alt) // 2
        cor = COR.get(self.lado, TRILHO)

        t.create_line(x0, cy, x1, cy, width=alt, capstyle="round", fill=cor)
        bx, r = x0 + (x1 - x0) * self.pos, alt // 2 - e(4)
        t.create_oval(bx - r, cy - r, bx + r, cy + r, fill=TEXTO, outline="")

        for tipo, x, ancora in (("wifi", cx - e(52), "e"), ("ethernet", cx + e(52), "w")):
            t.create_text(x, cy, text=ROTULO[tipo], anchor=ancora,
                          fill=TEXTO if self.lado == tipo else APAGADO,
                          font=("Segoe UI Semibold", 12))
        t.create_text(cx, e(76), text=self.msg, fill=APAGADO, font=("Segoe UI", 8))

    def animar(self):
        alvo = POSICAO[self.lado]
        self.pos += (alvo - self.pos) * 0.3
        if abs(alvo - self.pos) < 0.01:
            self.pos = alvo
        self.desenhar()
        if self.pos != alvo:
            self.after(12, self.animar)

    # ---------- mouse: arrastar move, clicar troca ----------
    def pressionar(self, ev):
        self.arrasto = (ev.x_root, ev.y_root, self.winfo_x(), self.winfo_y(), False)

    def arrastar(self, ev):
        x0, y0, jx, jy, movendo = self.arrasto
        dx, dy = ev.x_root - x0, ev.y_root - y0
        if movendo or abs(dx) + abs(dy) > self.e(5):
            self.arrasto = (x0, y0, jx, jy, True)
            self.geometry(f"+{jx + dx}+{jy + dy}")

    def soltar(self, ev):
        if self.arrasto and self.arrasto[4]:
            self.salvar()
        else:
            self.clique(ev)
        self.arrasto = None

    def menu(self, ev):
        m = tk.Menu(self, tearoff=0)
        topo = tk.BooleanVar(value=self.cfg.get("topo", False))
        inicio = tk.BooleanVar(value=inicia_com_windows())
        m.add_checkbutton(label="Sempre visível", variable=topo,
                          command=lambda: self.fixar(topo.get()))
        m.add_checkbutton(label="Iniciar com o Windows", variable=inicio,
                          command=lambda: self.iniciar(inicio.get()))
        m.add_separator()
        m.add_command(label="Fechar", command=self.destroy)
        m.tk_popup(ev.x_root, ev.y_root)

    def fixar(self, topo):
        self.cfg["topo"] = topo
        self.attributes("-topmost", topo)
        self.salvar()

    def iniciar(self, ligar):
        if self.ocupado:
            return
        self.ocupado, self.msg = True, "Configurando…"
        self.desenhar()
        self.em_segundo_plano(lambda: definir_inicio(ligar))

    # ---------- troca ----------
    def clique(self, evento):
        if self.ocupado:
            return
        if self.lado:
            destino = "ethernet" if self.lado == "wifi" else "wifi"
        else:  # estado indefinido: vale o lado em que se clicou
            destino = "ethernet" if getattr(evento, "x", 0) > self.e(LARG / 2) else "wifi"
        if destino not in self.ads or len(self.ads) < 2:
            return
        self.ocupado, self.lado, self.msg = True, destino, "Trocando…"
        self.animar()
        self.em_segundo_plano(lambda: trocar_para(destino, self.ads))

    def em_segundo_plano(self, acao):
        """Roda a ação fora da interface e depois relê o estado real da rede."""
        def tarefa():
            erro = None
            try:
                acao()
            except Exception as ex:
                erro = str(ex)
            try:
                ads = adaptadores()
            except Exception as ex:
                ads, erro = self.ads, erro or str(ex)
            self.resultado = (ads, erro)

        def aguardar():  # o Tk só pode ser tocado pela thread principal
            if self.resultado is None:
                self.after(50, aguardar)
            else:
                self.atualizar(*self.resultado)

        self.resultado = None
        threading.Thread(target=tarefa, daemon=True).start()
        aguardar()

    def atualizar(self, ads, erro):
        self.ads, self.lado, self.ocupado = ads, estado(ads), False
        faltam = [ROTULO[t] for t in ROTULO if t not in ads]
        if erro:
            self.msg = erro[:55]
        elif faltam:
            self.msg = "Adaptador não encontrado: " + ", ".join(faltam)
        elif self.lado:
            self.msg = ads[self.lado][0] + " ativo"
        else:
            self.msg = "Clique no lado desejado"
        self.animar()


def main():
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Habilitar/desabilitar adaptadores exige administrador: reabre elevado.
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{os.path.abspath(sys.argv[0])}"', None, 1)
        return
    ctypes.windll.kernel32.CreateMutexW(None, False, "InterruptorDeRede.Instancia")
    if ctypes.windll.kernel32.GetLastError() == 183:  # já está aberto
        return
    Interruptor().mainloop()


if __name__ == "__main__":
    main()
