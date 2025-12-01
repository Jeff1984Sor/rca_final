import wmi
import psutil
import platform
import socket
import requests
import json
import sys

# --- CONFIGURAÇÃO ---
# Se for testar no seu próprio PC, use 127.0.0.1:8000
# Se for rodar em outro PC da rede, troque pelo IP do seu PC (ex: 192.168.0.15:8000)
URL_API = "http://127.0.0.1:8000/equipamentos/api/atualizar-hardware/" 

def coletar_e_enviar():
    print("--- INICIANDO AUDITORIA ---")
    
    # 1. Conecta ao Windows (WMI)
    try:
        c = wmi.WMI()
    except:
        print("Erro: Este script só funciona em Windows.")
        return

    info = {}

    # 2. Dados Básicos
    print("Lendo Hostname e SO...")
    info['hostname'] = socket.gethostname()
    info['os'] = f"{platform.system()} {platform.release()} ({platform.version()})"
    
    # 3. Serial Dell (BIOS)
    print("Lendo Serial da BIOS...")
    try:
        bios = c.Win32_Bios()[0]
        info['serial_number'] = bios.SerialNumber.strip()
    except:
        info['serial_number'] = "GENERICO" # Caso não consiga ler

    # 4. Processador
    info['cpu'] = platform.processor()

    # 5. Memória RAM
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    info['ram'] = f"{ram_gb} GB"

    # 6. Disco C:
    try:
        disk = psutil.disk_usage('C:\\')
        total = round(disk.total / (1024**3), 2)
        livre = round(disk.free / (1024**3), 2)
        info['disk'] = f"Total: {total} GB (Livre: {livre} GB)"
    except:
        info['disk'] = "Erro Disco"

    # 7. Softwares (Pega os 50 primeiros para ser rápido)
    print("Lendo softwares instalados...")
    softs = []
    try:
        # Método rápido via WMI
        for p in c.Win32_Product():
            if p.Name:
                softs.append(p.Name)
    except:
        softs.append("Erro ao ler softwares ou permissão negada")
    
    info['softwares'] = ", ".join(softs[:50])

    # --- ENVIAR PARA O DJANGO ---
    print(f"\nEnviando dados para {URL_API}...")
    try:
        response = requests.post(URL_API, json=info)
        
        if response.status_code == 200:
            print("\n✅ SUCESSO! Dados atualizados no Django.")
            print("Resposta do Servidor:", response.json())
        else:
            print(f"\n❌ ERRO DO SERVIDOR ({response.status_code}):")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERRO DE CONEXÃO: O servidor Django está rodando?")
        print("Verifique se digitou 'python manage.py runserver'")

if __name__ == "__main__":
    coletar_e_enviar()