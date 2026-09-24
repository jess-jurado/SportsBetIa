import pandas as pd
from engine.storage import get_analytics_data, clean_old_records
import datetime

def generate_executive_report():
    print(f"\n=======================================================")
    print(f"=== REPORTE EJECUTIVO BetIA | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    print(f"=======================================================\n")
    
    try:
        top_5, by_sport, hourly = get_analytics_data()
        
        print("[1] 🏆 TOP 5 MEJORES OPORTUNIDADES HISTÓRICAS (Últimas 24h)")
        print("-" * 55)
        if not top_5.empty:
            print(top_5.to_string(index=False))
        else:
            print(" -> Sin oportunidades de arbitraje captadas hoy.")

        print("\n\n[2] 📈 ANÁLISIS DE VOLUMEN DE OPORTUNIDADES POR DEPORTE")
        print("-" * 55)
        if not by_sport.empty:
            print(by_sport.to_string(index=False))
        else:
            print(" -> Insuficiente data etiquetada purgada.")

        print("\n\n[3] 🕖 HEATMAP: RENTABILIDAD PROMEDIO SEGÚN LA HORA")
        print("-" * 55)
        if not hourly.empty:
            print(hourly.to_string(index=False))
        else:
            print(" -> Insuficiente data etiquetada.")
            
        print("\n\n[4] 🧹 INICIANDO LIMPIEZA DE GARBAGE COLLECTOR SQlite...")
        print("-" * 55)
        clean_old_records()
        print(" -> Todos los registros basura con más de 7 días purgados correctamente.")
        print(" -> Rendimiento DB Optimizado.\n")
        
    except Exception as e:
        print(f"Error generando reporte: {e}")
        print("Aviso: Probablemente el main.py de fondo está bloqueando la memoria Base en Lectura exclusiva.\n")
        
    print("=================== FIN DEL REPORTE ===================\n")

if __name__ == "__main__":
    generate_executive_report()
