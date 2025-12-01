import wmi
import psutil
import platform
import socket
import requests
import json
import sys

# --- CONFIGURAÇÃO ---
# Troque pelo IP do seu servidor Django. Se for local, use localhost:8000
URL_API = "http://127.0.0.1:8000/equipamentos/api/atualizar-hardware/" 

def coletar_dados():
    print("Iniciando varredura de hardware...")
    c = wmi.WMI()
    info = {}

    # 1. Identificação Básica
    info['hostname'] = socket.gethostname()
    info['os'] = f"{platform.system()} {platform.release()} ({platform.version()})"
    
    # 2. BIOS / Serial Dell
    # Isso pega o Serial Number da placa mãe (Service Tag)
    try:
        bios = c.Win32_Bios()[0]
        info['serial_number'] = bios.SerialNumber.strip()
    except:
        info['serial_number'] = "DESCONHECIDO"

    # 3. Processador
    info['cpu'] = platform.processor()

    # 4. Memória RAM (Formatada em GB)
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    info['ram'] = f"{ram_gb} GB"

    # 5. Disco C: (Formatado em GB)
    try:
        disk = psutil.disk_usage('C:\\')
        total_gb = round(disk.total / (1024**3), 2)
        livre_gb = round(disk.free / (1024**3), 2)
        info['disk'] = f"Total: {total_gb} GB (Livre: {livre_gb} GB)"
    except:
        info['disk'] = "Erro ao ler disco C"

    # 6. Softwares Instalados (Versão Rápida via WMI)
    # Nota: Ler todos os softwares pode demorar. Vamos pegar os processos principais ou usar WMI
    print("Lendo softwares instalados (isso pode levar alguns segundos)...")
    softwares_lista = []
    
    # Método via Registro do Windows é melhor, mas WMI é mais simples para este exemplo
    # Se ficar muito lento, remova este bloco try/except
    try:
        # Busca softwares instalados via WMI (pode ser lento em alguns PCs)
        for product in c.Win32_Product():
            if product.Name:
                softwares_lista.append(product.Name)
    except:
        softwares_lista.append("Não foi possível ler a lista completa via WMI")

    info['softwares'] = ", ".join(softwares_lista) # Junta tudo numa string

    return info

def enviar_dados(dados):
    print(f"Enviando dados de: {dados['hostname']} (Serial: {dados['serial_number']})")
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(URL_API, data=json.dumps(dados), headers=headers)
        
        if response.status_code == 200:
            print("SUCESSO! Equipamento atualizado no Django.")
            print(response.json())
        else:
            print(f"ERRO API: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"ERRO DE CONEXÃO: {e}")
        print("Verifique se o servidor Django está rodando e acessível.")

if __name__ == "__main__":
    try:
        dados_pc = coletar_dados()
        enviar_dados(dados_pc)
    except Exception as e:
        print(f"Erro fatal: {e}")
    
    input("\nPressione ENTER para fechar...")