# lexer.py
import ply.lex as lex

lexical_errors_list = []

# Lista de tokens actualizada: Ahora incluye WHILE
tokens = (
    'ID',
    'NUMBER',
    'PLUS',
    'MINUS',
    'TIMES',
    'DIVIDE',
    'LPAREN',
    'RPAREN',
    'EQUAL', # Operador de asignación

    # Nuevos tokens para operadores de comparación
    'LT',       # <
    'LE',       # <=
    'GT',       # >
    'GE',       # >=
    'EQ',       # ==
    'NE',       # !=

    # Nuevos tokens para operadores lógicos/booleanos
    'AND',      # AND
    'OR',       # OR
    'NOT',      # NOT

    # Nuevos tokens para estructuras de control (IF, ELSE ya estaban, añadimos WHILE)
    'IF',       # IF
    'ELSE',     # ELSE
    'WHILE',    # WHILE
    'LBRACE',   # {
    'RBRACE',   # }
)

# Palabras clave reservadas (Añadimos 'WHILE')
reserved = {
    'IF'    : 'IF',
    'ELSE'  : 'ELSE',
    'WHILE' : 'WHILE', # <--- NUEVO
    'AND'   : 'AND',
    'OR'    : 'OR',
    'NOT'   : 'NOT',
}

# Reglas de expresiones regulares para los tokens
t_PLUS      = r'\+'
t_MINUS     = r'-'
t_TIMES     = r'\*'
t_DIVIDE    = r'/'
t_LPAREN    = r'\('
t_RPAREN    = r'\)'
t_EQUAL     = r'='

# Reglas para operadores de comparación (orden importante: los de dos caracteres primero)
t_LE        = r'<='
t_GE        = r'>='
t_EQ        = r'=='
t_NE        = r'!='
t_LT        = r'<'
t_GT        = r'>'

# Reglas para las llaves de los bloques
t_LBRACE    = r'\{'
t_RBRACE    = r'\}'

# Ignorar espacios y tabulaciones
t_ignore = ' \t'

# Regla para comentarios de una línea (Python-style)
def t_COMMENT(t):
    r'\#.*'
    pass # No hacer nada con los comentarios, simplemente ignorarlos

# Regla para identificadores (variables y palabras clave)
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    # Verificar si el ID es una palabra clave reservada
    t.type = reserved.get(t.value.upper(), 'ID')
    return t

# Regla para números (enteros y decimales)
def t_NUMBER(t):
    r'\d+(\.\d*)?|\.\d+'
    t.value = float(t.value) # Siempre convertir a flotante por ahora para simplificar el manejo de tipos
    return t

# Regla para contar las líneas
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Manejo de errores de caracteres ilegales
def t_error(t):
    line_start_pos = t.lexer.lexdata.rfind('\n', 0, t.lexpos)
    column = (t.lexpos - line_start_pos) if line_start_pos != -1 else t.lexpos
    
    lexical_errors_list.append({
        "type": "Léxico",
        "message": f"Caracter ilegal '{t.value[0]}'",
        "line": t.lineno,
        "column": column
    })
    t.lexer.skip(1)

lexer = lex.lex()

def get_lexical_errors():
    return lexical_errors_list

def reset_lexical_errors():
    global lexical_errors_list
    lexical_errors_list = []

# Función para probar el lexer directamente (opcional, para depuración)
def test_lexer(data):
    reset_lexical_errors()
    lexer.input(data)
    tokens_list = []
    print(f"--- Lexing: '{data.strip()}' ---")
    while True:
        tok = lexer.token()
        if not tok:
            break
        tokens_list.append(tok)
        print(tok)
    errors = get_lexical_errors()
    if errors:
        print("\n--- Errores Léxicos Detectados ---")
        for error in errors:
            print(f"{error['type']}: {error['message']} (Línea: {error['line']}, Columna: {error['column']})")
    print("\n")
    return tokens_list, errors

if __name__ == '__main__':
    test_lexer("contador = 0 WHILE (contador < 5) { contador = contador + 1 }")
    test_lexer("IF (cond) { x = 1 } ELSE { y = 2 }")
    test_lexer("ilegal_char = $")