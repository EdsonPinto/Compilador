# app.py
import streamlit as st
import gramatica
from streamlit_ace import st_ace
import pandas as pd
import graphviz

# Configuración básica de la página de Streamlit
st.set_page_config(
    page_title="Compilador Sencillo",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Título y descripción ---
st.title("Compilador de Expresiones Aritméticas Simples")
st.markdown("""
Este es un compilador básico que realiza análisis léxico, sintáctico, semántico (verificación de declaración de variables, **tipos**)
y ahora también **interpreta** el código para mostrar los resultados de las operaciones y asignaciones, incluyendo **operadores lógicos/comparación, estructuras `if/else`, y bucles `while`**.
""")

# --- Sidebar con información del compilador ---
st.sidebar.header("Acerca del Compilador")
st.sidebar.info(
    """
    **Fases implementadas:**
    - **Análisis Léxico:** Convierte el código fuente en tokens, ignorando comentarios (`#`).
    - **Análisis Sintáctico:** Verifica la estructura del código y genera un Árbol de Sintaxis Abstracta (AST).
    - **Análisis Semántico:** Verifica reglas de significado (ej. variables declaradas, **compatibilidad de tipos**, condición booleana en `IF`/`WHILE`).
    - **Interpretación:** Ejecuta el AST para calcular los valores de las variables y evaluar expresiones lógicas/condiciones, incluyendo el control de flujo.

    **Nuevas características del lenguaje:**
    - **Comentarios:** `#` para comentarios de una línea.
    - **Operadores de Comparación:** `>`, `<`, `>=`, `<=`, `==`, `!=`.
    - **Operadores Lógicos:** `AND`, `OR`, `NOT`.
    - **Estructuras de Control:** `IF (condicion) { ... } ELSE { ... }`, `WHILE (condicion) { ... }`.
    - **Tipos de Datos:** Inferencia y comprobación básica de `float` y `boolean`.

    **Advertencias conocidas:**
    - Se han detectado 2 conflictos `shift/reduce` en la gramática, pero PLY los resuelve por defecto priorizando el `shift`, lo cual es el comportamiento esperado para expresiones aritméticas.
    """
)

st.markdown("---")

# --- Inicialización de st.session_state para historial y editor ---
# 'code_history' almacena las entradas de código previas
if 'code_history' not in st.session_state:
    st.session_state.code_history = []
    default_code = """
# Ejemplos de código:
# Asignación y operaciones numéricas
edad = 25
salario = 1500 * 2
total = salario - (edad * 10) # 3000 - 250 = 2750

# Operadores de comparación y lógicos
es_adulto = edad >= 18
es_rico = salario > 2000 AND es_adulto # True AND True -> True
resultado_logico = es_rico OR NOT es_adulto # (True) OR NOT (True) -> True OR False -> True

# Estructura IF/ELSE
IF (es_rico) {
    mensaje = 1 # Se ejecuta este bloque
    bonus = salario * 0.1
} ELSE {
    mensaje = 0
    bonus = 0
}

# Bucle WHILE
contador = 0
suma = 0
WHILE (contador < 5) {
    suma = suma + contador # 0 + 1 + 2 + 3 + 4 = 10
    contador = contador + 1
}
final_contador = contador # Debería ser 5
final_suma = suma # Debería ser 10

# --- Ejemplos que generan errores ---

# Variable no declarada (error semántico)
# resultado_final = total + variable_inexistente + 10

# Prueba de división por cero (error de ejecución semántico)
# cero = 0
# division_por_cero = 100 / cero

# Prueba de error de tipo (suma de float y booleano)
# val_num = 10.5
# val_bool = True
# suma_erronea = val_num + val_bool

# Prueba de error de tipo en condición WHILE
# num_loop = 10
# WHILE (num_loop + 5) { # Error: condición no booleana
#    num_loop = num_loop - 1
# }

# Caracter ilegal (error léxico)
# bad_char = $
"""
    st.session_state.code_history.insert(0, default_code.strip())

# 'current_code' mantiene el código actual en el editor
if 'current_code' not in st.session_state:
    # Inicializa con el default_code si no hay nada en el historial o si no se ha establecido
    st.session_state.current_code = default_code.strip()

# 'code_to_process_on_rerun' es el flag que dispara la compilación en la siguiente ejecución
if 'code_to_process_on_rerun' not in st.session_state:
    st.session_state.code_to_process_on_rerun = None # Inicialmente no hay código para procesar

# 'error_annotations_for_rerun' almacena las anotaciones para el editor Ace
if 'error_annotations_for_rerun' not in st.session_state:
    st.session_state.error_annotations_for_rerun = []


# --- Área de entrada de código con resaltado de sintaxis ---
st.header("Código de Entrada")

# Eliminamos la sección de "Seleccionar código del historial"
# if st.session_state.code_history:
#     newline_char = '\n'
#     history_options = [
#         f"Entrada {i+1}: {entry[:50].replace(newline_char, ' ')}..." if len(entry) > 50 else f"Entrada {i+1}: {entry.splitlines()[0].strip()}"
#         for i, entry in enumerate(st.session_state.code_history)
#     ]
#     selected_history_index = st.selectbox(
#         "Seleccionar código del historial:",
#         options=range(len(history_options)),
#         format_func=lambda x: history_options[x],
#         key="history_selector"
#     )
#     if st.session_state.current_code != st.session_state.code_history[selected_history_index]:
#         st.session_state.current_code = st.session_state.code_history[selected_history_index]
#         st.session_state.error_annotations_for_rerun = []
#         st.session_state.code_to_process_on_rerun = None
#         st.rerun()

# Usamos st_ace para el editor de código, pasando las anotaciones si hay
user_code = st_ace(
    value=st.session_state.current_code, # Usa el código guardado en session_state
    language="python",
    theme="dracula",
    height=550,
    key="ace_editor",
    font_size=14,
    show_gutter=True,
    wrap=True,
    auto_update=False,
    annotations=st.session_state.error_annotations_for_rerun
)

# Siempre actualiza el código en la sesión con el valor actual del editor.
st.session_state.current_code = user_code


# --- Botón para compilar ---
compile_button_pressed = st.button("Compilar y Ejecutar Código", key="compile_button")

if compile_button_pressed:
    st.session_state.error_annotations_for_rerun = []
    
    if not st.session_state.current_code.strip():
        st.warning("El código de entrada está vacío. Por favor, introduce código para compilar.")
        st.session_state.code_to_process_on_rerun = None
    else:
        # Añadir el código actual al historial si es nuevo y no está vacío
        if st.session_state.current_code.strip() not in st.session_state.code_history:
            st.session_state.code_history.insert(0, st.session_state.current_code.strip())
            if len(st.session_state.code_history) > 10:
                st.session_state.code_history = st.session_state.code_history[:10]
        
        st.session_state.code_to_process_on_rerun = st.session_state.current_code
    
    st.rerun()


# Procesar el código si hay un 'code_to_process_on_rerun' establecido
if st.session_state.code_to_process_on_rerun is not None:
    code_to_compile = st.session_state.code_to_process_on_rerun
    st.session_state.code_to_process_on_rerun = None

    st.markdown("---")
    st.header("Resultados del Análisis y Ejecución")

    ast, errors, evaluated_results = gramatica.parse_and_interpret_code(code_to_compile)

    if errors:
        st.error("¡Se detectaron errores en el código!")
        new_annotations = []
        for err in errors:
            if err.get('line') is not None:
                new_annotations.append({
                    "row": err['line'] - 1,
                    "column": err.get('column', 0),
                    "text": f"{err['type']}: {err['message']}",
                    "type": "error"
                })
            st.markdown(
                f"**Tipo: {err['type']}**\n\n"
                f"**Mensaje**: {err['message']}\n\n"
                f"**Línea**: {err.get('line', 'N/A')}\n\n"
                f"**Columna**: {err.get('column', 'N/A')}\n\n"
            )
            st.markdown("---")
        
        st.session_state.error_annotations_for_rerun = new_annotations

    else:
        st.success("¡Análisis y Ejecución Completados sin errores!")
        st.session_state.error_annotations_for_rerun = []

        st.subheader("Árbol de Sintaxis Abstracta (AST)")
        st.write("El AST representa la estructura jerárquica de tu código. Es la salida del análisis sintáctico.")
        
        if ast:
            try:
                dot_graph = gramatica.generate_ast_graph(ast)
                st.graphviz_chart(dot_graph)
                st.download_button(
                    label="Descargar AST (PNG)",
                    data=dot_graph.pipe(format='png'),
                    file_name="ast_compilador.png",
                    mime="image/png"
                )
            except Exception as e:
                st.warning(f"No se pudo generar el gráfico del AST. Asegúrate de tener Graphviz instalado y configurado correctamente. Error: {e}")
                st.code(ast, language='python')
        else:
            st.info("No se generó un AST válido para mostrar.")
            st.code(ast, language='python')

        st.subheader("Tabla de Símbolos Final")
        st.write("Contiene las variables declaradas, sus tipos inferidos y sus valores finales después de la ejecución.")
        
        symbol_table_data = []
        for name, info in gramatica.get_symbol_table().items():
            if info.get('type') != 'unknown_error':
                symbol_table_data.append({
                    "Nombre Variable": name,
                    "Tipo": info.get('type', 'N/A'),
                    "Valor Final": info.get('evaluated_value', 'N/A')
                })
        
        if symbol_table_data:
            df_symbol_table = pd.DataFrame(symbol_table_data)
            st.dataframe(df_symbol_table, use_container_width=True)
        else:
            st.info("La tabla de símbolos está vacía o solo contiene entradas de error.")


        st.subheader("Resultados Evaluados de Variables")
        st.write("Estos son los valores finales de las variables después de la ejecución del código.")
        if evaluated_results:
            st.json(evaluated_results)
        else:
            st.info("No hay resultados de variables para mostrar (quizás solo expresiones sin asignación o errores en la ejecución).")
        
    st.session_state.code_to_process_on_rerun = None

st.markdown("---")
st.info("Desarrollado con Python y PLY para la asignatura de Compiladores.")
