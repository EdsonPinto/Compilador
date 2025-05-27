# gramatica.py
import ply.yacc as yacc
import lexer # Importa el archivo lexer.py
import graphviz

# Listas para almacenar errores de las diferentes fases
syntactic_errors_list = []
semantic_errors_list = []

# Tabla de símbolos: Almacenará {nombre_ID: {'value_ast': ..., 'evaluated_value': ..., 'type': ...}}
symbol_table = {}

# Obtenemos la lista de tokens del lexer.py
tokens = lexer.tokens

# Función para añadir errores semánticos de forma estructurada
def add_semantic_error(message, line, column):
    semantic_errors_list.append({
        "type": "Semántico",
        "message": message,
        "line": line,
        "column": column
    })

# Símbolo de inicio de la gramática
start = 'program'

# Precedencia de operadores (de menor a mayor, con más operadores añadidos)
# Las reglas de precedencia resuelven los conflictos shift/reduce automáticamente
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
    ('left', 'EQ', 'NE'), # Igualdad y Desigualdad
    ('left', 'LT', 'LE', 'GT', 'GE'), # Comparación (menos precedencia que igualdad)
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS'), # Para la negación unaria (ej. -5)
)

# --- Funciones auxiliares para el manejo de tipos ---
def get_node_type(node, current_symbol_table):
    """
    Intenta inferir el tipo de un nodo del AST.
    Utiliza la tabla de símbolos para obtener el tipo de los IDs.
    """
    if isinstance(node, tuple):
        node_type = node[0] # El primer elemento de la tupla es el tipo de nodo AST

        if node_type == 'number':
            return 'float' # Todos los números son tratados como float por ahora
        elif node_type == 'id':
            var_name = node[1]
            if var_name in current_symbol_table and 'type' in current_symbol_table[var_name]:
                return current_symbol_table[var_name]['type']
            return 'unknown' # Tipo desconocido si no está en la tabla de símbolos o no tiene tipo
        elif node_type in ('+', '-', '*', '/'):
            # Las operaciones aritméticas esperan flotantes y devuelven flotantes
            left_type = get_node_type(node[1], current_symbol_table)
            right_type = get_node_type(node[2], current_symbol_table)
            if left_type == 'float' and right_type == 'float':
                return 'float'
            return 'error' # Indica un error de tipo
        elif node_type in ('<', '<=', '>', '>=', '==', '!='):
            # Las comparaciones esperan flotantes o booleanos y devuelven booleanos
            return 'boolean'
        elif node_type in ('AND', 'OR', 'NOT'):
            # Las operaciones lógicas esperan booleanos y devuelven booleanos
            return 'boolean'
        elif node_type == 'uminus':
            # La negación unaria mantiene el tipo del operando (espera float)
            return get_node_type(node[1], current_symbol_table)
    return 'unknown' # Tipo por defecto para nodos no reconocidos o complejos

def check_type_compatibility(op, type1, type2, p_lineno, p_lexpos):
    """
    Verifica la compatibilidad de tipos para operaciones binarias.
    Añade un error semántico si los tipos son incompatibles.
    """
    if type1 == 'unknown' or type2 == 'unknown':
        # Si alguno de los tipos es desconocido, no podemos verificar la compatibilidad.
        # Esto podría ser el resultado de una variable no declarada.
        return 'unknown'
    
    if op in ('+', '-', '*', '/'):
        if type1 == 'float' and type2 == 'float':
            return 'float'
        else:
            add_semantic_error(f"Error de tipo: Operación '{op}' no definida para '{type1}' y '{type2}'.", p_lineno, p_lexpos)
            return 'error'
    elif op in ('<', '<=', '>', '>=', '==', '!='):
        # Las comparaciones numéricas son entre flotantes.
        # Las comparaciones de igualdad/desigualdad también pueden ser entre booleanos.
        if (type1 == 'float' and type2 == 'float') or \
           (type1 == 'boolean' and type2 == 'boolean' and op in ('==', '!=')):
            return 'boolean'
        else:
            add_semantic_error(f"Error de tipo: Comparación '{op}' no definida para '{type1}' y '{type2}'.", p_lineno, p_lexpos)
            return 'error'
    elif op in ('AND', 'OR'):
        # Las operaciones lógicas son entre booleanos.
        if type1 == 'boolean' and type2 == 'boolean':
            return 'boolean'
        else:
            add_semantic_error(f"Error de tipo: Operación lógica '{op}' no definida para '{type1}' y '{type2}'.", p_lineno, p_lexpos)
            return 'error'
    return 'unknown' # Tipo por defecto si el operador no está cubierto

# --- Reglas de la gramática (Producciones) ---

# Regla inicial del programa
def p_program(p):
    '''program : statements'''
    p[0] = p[1] # El programa es una secuencia de sentencias

# Reglas para manejar múltiples sentencias
def p_statements_recursive(p):
    '''statements : statements statement'''
    p[0] = p[1] + [p[2]]

def p_statements_single(p):
    '''statements : statement'''
    p[0] = [p[1]]

# Regla para la sentencia de asignación: ID = expression
def p_statement_assign(p):
    'statement : ID EQUAL expression'
    var_name = p[1]
    value_expr_ast = p[3] # AST de la expresión del lado derecho

    # Infiere el tipo de la expresión que se va a asignar
    inferred_type = get_node_type(value_expr_ast, symbol_table)

    # Almacena la información de la variable en la tabla de símbolos
    symbol_table[var_name] = {
        'value_ast': value_expr_ast, # El AST de la expresión que define su valor
        'evaluated_value': None,     # El valor real después de la interpretación
        'type': inferred_type        # El tipo inferido de la variable
    }
    # Construye el nodo AST para la asignación
    p[0] = ('assign', var_name, value_expr_ast)


def p_statement_expression(p):
    'statement : expression'
    p[0] = p[1]

# Regla para la estructura de control IF-ELSE
def p_statement_if(p):
    '''statement : IF LPAREN expression RPAREN block
                 | IF LPAREN expression RPAREN block ELSE block'''
    condition_expr = p[3]
    
    # Comprobación semántica: La condición del IF debe ser booleana
    condition_type = get_node_type(condition_expr, symbol_table)
    if condition_type != 'boolean' and condition_type != 'unknown':
        add_semantic_error(f"Error de tipo: La condición IF debe ser booleana, se encontró '{condition_type}'.", p.lineno(1), p.lexpos(1))

    if len(p) == 6: # IF (expr) block
        p[0] = ('if', condition_expr, p[5]) # AST: ('if', condicion_expr_AST, bloque_then_AST)
    else: # IF (expr) block ELSE block
        p[0] = ('if_else', condition_expr, p[5], p[7]) # AST: ('if_else', condicion_expr_AST, bloque_then_AST, bloque_else_AST)

# Regla para la estructura de control WHILE
def p_statement_while(p):
    '''statement : WHILE LPAREN expression RPAREN block'''
    condition_expr = p[3]
    
    # Comprobación semántica: La condición del WHILE debe ser booleana
    condition_type = get_node_type(condition_expr, symbol_table)
    if condition_type != 'boolean' and condition_type != 'unknown':
        add_semantic_error(f"Error de tipo: La condición WHILE debe ser booleana, se encontró '{condition_type}'.", p.lineno(1), p.lexpos(1))
    
    p[0] = ('while', condition_expr, p[5]) # AST: ('while', condicion_expr_AST, bloque_a_repetir_AST)

# Regla para un bloque de sentencias (entre llaves o una sola sentencia)
def p_block(p):
    '''block : LBRACE statements RBRACE''' # <--- CAMBIO AQUÍ: Eliminada '| statement'
    p[0] = p[2]


def p_expression_binop(p):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression'''
    left_expr_ast = p[1]
    operator = p[2]
    right_expr_ast = p[3]
    left_type = get_node_type(left_expr_ast, symbol_table)
    right_type = get_node_type(right_expr_ast, symbol_table)
    result_type = check_type_compatibility(operator, left_type, right_type, p.lineno(2), p.lexpos(2))
    if result_type == 'error':
        p[0] = ('error', operator, left_expr_ast, right_expr_ast, "Tipo incompatible")
    else:
        p[0] = (operator, left_expr_ast, right_expr_ast)

def p_expression_comparison(p):
    '''expression : expression LT expression
                  | expression LE expression
                  | expression GT expression
                  | expression GE expression
                  | expression EQ expression
                  | expression NE expression'''
    left_expr_ast = p[1]
    operator = p[2]
    right_expr_ast = p[3]
    left_type = get_node_type(left_expr_ast, symbol_table)
    right_type = get_node_type(right_expr_ast, symbol_table)
    result_type = check_type_compatibility(operator, left_type, right_type, p.lineno(2), p.lexpos(2))
    if result_type == 'error':
        p[0] = ('error', operator, left_expr_ast, right_expr_ast, "Tipo incompatible en comparación")
    else:
        p[0] = (operator, left_expr_ast, right_expr_ast)

def p_expression_logical(p):
    '''expression : expression AND expression
                  | expression OR expression'''
    left_expr_ast = p[1]
    operator = p[2]
    right_expr_ast = p[3]
    left_type = get_node_type(left_expr_ast, symbol_table)
    right_type = get_node_type(right_expr_ast, symbol_table)
    result_type = check_type_compatibility(operator, left_type, right_type, p.lineno(2), p.lexpos(2))
    if result_type == 'error':
        p[0] = ('error', operator, left_expr_ast, right_expr_ast, "Tipo incompatible en operación lógica")
    else:
        p[0] = (operator, left_expr_ast, right_expr_ast)

def p_expression_not(p):
    'expression : NOT expression'
    expr_ast = p[2]
    expr_type = get_node_type(expr_ast, symbol_table)
    if expr_type != 'boolean' and expr_type != 'unknown':
        add_semantic_error(f"Error de tipo: Operador 'NOT' solo aplica a booleanos, se encontró '{expr_type}'.", p.lineno(1), p.lexpos(1))
        p[0] = ('error', 'NOT', expr_ast, "Tipo incompatible para NOT")
    else:
        p[0] = ('NOT', expr_ast)

def p_expression_uminus(p):
    'expression : MINUS expression %prec UMINUS'
    p[0] = ('uminus', p[2])

def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]

def p_expression_number(p):
    'expression : NUMBER'
    p[0] = ('number', p[1])

def p_expression_id(p):
    'expression : ID'
    var_name = p[1]
    if var_name not in symbol_table:
        add_semantic_error(f"Variable '{var_name}' no declarada.", p.lineno(1), p.lexpos(1))
        symbol_table[var_name] = {'type': 'unknown_error', 'value_ast': None, 'evaluated_value': None}
    p[0] = ('id', var_name)

def p_error(t):
    global syntactic_errors_list
    if t:
        line_start_pos = t.lexer.lexdata.rfind('\n', 0, t.lexpos)
        column = (t.lexpos - line_start_pos) if line_start_pos != -1 else t.lexpos
        error_message = f"Error sintáctico cerca de '{t.value}'"
        syntactic_errors_list.append({
            "type": "Sintáctico",
            "message": error_message,
            "line": t.lineno,
            "column": column,
            "token": t.value
        })
    else:
        syntactic_errors_list.append({
            "type": "Sintáctico",
            "message": "Error sintáctico: Fin de archivo inesperado o incompleto.",
            "line": None,
            "column": None,
            "token": "EOF"
        })

# Construir el parser con debug=True para generar parser.out
parser = yacc.yacc(debug=True) # <--- ¡Aquí está el cambio!

# --- Funciones para acceder y resetear las listas de errores y la tabla de símbolos ---
def get_syntactic_errors(): return syntactic_errors_list
def reset_syntactic_errors(): global syntactic_errors_list; syntactic_errors_list = []
def get_semantic_errors(): return semantic_errors_list
def reset_semantic_errors(): global semantic_errors_list; semantic_errors_list = []
def get_symbol_table(): return symbol_table
def reset_symbol_table(): global symbol_table; symbol_table = {}

# --- Intérprete para evaluar el AST ---
def evaluate_ast(node, current_symbol_table):
    """
    Recorre el Árbol de Sintaxis Abstracta (AST) y calcula su valor.
    current_symbol_table: la tabla de símbolos actual para resolver IDs y almacenar valores.
    """
    if isinstance(node, tuple):
        node_type = node[0]

        if node_type == 'number':
            return node[1]
        elif node_type == 'id':
            var_name = node[1]
            if var_name in current_symbol_table:
                if current_symbol_table[var_name]['evaluated_value'] is not None:
                    return current_symbol_table[var_name]['evaluated_value']
                elif current_symbol_table[var_name]['value_ast'] is not None:
                    value = evaluate_ast(current_symbol_table[var_name]['value_ast'], current_symbol_table)
                    current_symbol_table[var_name]['evaluated_value'] = value
                    return value
                else:
                    return None
            else:
                add_semantic_error(f"Variable '{var_name}' no definida durante la ejecución.", None, None)
                return None
        elif node_type in ('+', '-', '*', '/'):
            op = node_type
            left = evaluate_ast(node[1], current_symbol_table)
            right = evaluate_ast(node[2], current_symbol_table)
            
            if left is None or right is None:
                return None

            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                add_semantic_error(f"Error de ejecución: Operación '{op}' con tipos no numéricos.", None, None)
                return None

            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/':
                if right == 0:
                    add_semantic_error("Error de ejecución: División por cero.", None, None)
                    return float('inf')
                return left / right
        
        # Operaciones de comparación
        elif node_type in ('<', '<=', '>', '>=', '==', '!='):
            op = node_type
            left = evaluate_ast(node[1], current_symbol_table)
            right = evaluate_ast(node[2], current_symbol_table)
            
            if left is None or right is None:
                return None

            if op == '<': return left < right
            if op == '<=': return left <= right
            if op == '>': return left > right
            if op == '>=': return left >= right
            if op == '==': return left == right
            if op == '!=': return left != right
        
        # Operaciones lógicas
        elif node_type == 'AND':
            left = evaluate_ast(node[1], current_symbol_table)
            if left is None:
                return None
            if not isinstance(left, bool):
                add_semantic_error("Error de ejecución: Operación 'AND' con operando izquierdo no booleano.", None, None)
                return False
            if not left:
                return False # Cortocircuito para AND
            
            right = evaluate_ast(node[2], current_symbol_table)
            if right is None:
                return None
            if not isinstance(right, bool):
                add_semantic_error("Error de ejecución: Operación 'AND' con operando derecho no booleano.", None, None)
                return False
            return left and right
        
        elif node_type == 'OR':
            left = evaluate_ast(node[1], current_symbol_table)
            if left is None:
                return None
            if not isinstance(left, bool):
                add_semantic_error("Error de ejecución: Operación 'OR' con operando izquierdo no booleano.", None, None)
                return False
            if left:
                return True # Cortocircuito para OR
            
            right = evaluate_ast(node[2], current_symbol_table)
            if right is None:
                return None
            if not isinstance(right, bool):
                add_semantic_error("Error de ejecución: Operación 'OR' con operando derecho no booleano.", None, None)
                return False
            return left or right
        
        elif node_type == 'NOT':
            expr_val = evaluate_ast(node[1], current_symbol_table)
            if expr_val is None:
                return None
            if not isinstance(expr_val, bool):
                add_semantic_error("Error de ejecución: Operación 'NOT' con tipo no booleano.", None, None)
                return False
            return not expr_val

        elif node_type == 'uminus':
            val = evaluate_ast(node[1], current_symbol_table)
            if val is None:
                return None
            if not isinstance(val, (int, float)):
                 add_semantic_error("Error de ejecución: Negación unaria con tipo no numérico.", None, None)
                 return None
            return -val
        
        elif node_type == 'assign':
            var_name = node[1]
            evaluated_value = evaluate_ast(node[2], current_symbol_table)
            if evaluated_value is None:
                return None # No asignar si la evaluación falló
            current_symbol_table[var_name]['evaluated_value'] = evaluated_value
            return evaluated_value
        
        elif node_type == 'if':
            condition_result = evaluate_ast(node[1], current_symbol_table)
            if condition_result is None:
                return None
            
            if not isinstance(condition_result, bool):
                 add_semantic_error("Error de ejecución: La condición IF debe ser booleana.", None, None)
                 return None

            if condition_result:
                block_statements = node[2] # Bloque 'then'
                last_result = None
                for stmt in block_statements:
                    if isinstance(stmt, tuple) and stmt[0] == 'error': continue # Saltar sentencias con errores semánticos en el AST
                    last_result = evaluate_ast(stmt, current_symbol_table)
                    if last_result is None and (isinstance(stmt, tuple) and stmt[0] != 'assign'):
                        # Propagar fallo de evaluación si no es una asignación y falló
                        return None
                return last_result
            return None # Si la condición es False, no se ejecuta el bloque then
        
        elif node_type == 'if_else':
            condition_result = evaluate_ast(node[1], current_symbol_table)
            if condition_result is None:
                return None
            
            if not isinstance(condition_result, bool):
                 add_semantic_error("Error de ejecución: La condición IF/ELSE debe ser booleana.", None, None)
                 return None

            if condition_result:
                block_statements = node[2] # Bloque 'then'
            else:
                block_statements = node[3] # Bloque 'else'
            
            last_result = None
            for stmt in block_statements:
                if isinstance(stmt, tuple) and stmt[0] == 'error': continue
                stmt_result = evaluate_ast(stmt, current_symbol_table) # Corrected: stmt_result from evaluate_ast
                if stmt_result is None and (isinstance(stmt, tuple) and stmt[0] != 'assign'):
                    return None
                last_result = stmt_result # Corrected: assign stmt_result to last_result
            return last_result
        
        elif node_type == 'while':
            condition_expr = node[1]
            block_statements = node[2]
            
            last_result = None
            # Bucle de ejecución del WHILE
            while True:
                condition_result = evaluate_ast(condition_expr, current_symbol_table)
                if condition_result is None: # Si la condición no se pudo evaluar (ej. variable no definida)
                    return None
                
                if not isinstance(condition_result, bool):
                    add_semantic_error("Error de ejecución: La condición WHILE debe ser booleana.", None, None)
                    return None # Error de tipo en condición

                if not condition_result: # Si la condición es falsa, salimos del bucle
                    break
                
                # Ejecutar el bloque del bucle
                for stmt in block_statements:
                    if isinstance(stmt, tuple) and stmt[0] == 'error': continue
                    stmt_result = evaluate_ast(stmt, current_symbol_table) # Corrected: stmt_result from evaluate_ast
                    if stmt_result is None and (isinstance(stmt, tuple) and stmt[0] != 'assign'):
                        return None
                    last_result = stmt_result # Corrected: assign stmt_result to last_result
            return last_result

        elif node_type == 'error': # Manejar nodos de error generados por comprobación de tipos
            # No intentar evaluar un nodo que ya se marcó como error semántico
            return None

    # Si el nodo es la lista de sentencias del programa principal (la raíz del AST)
    if isinstance(node, list):
        last_result = None
        for stmt_ast in node:
            if isinstance(stmt_ast, tuple) and stmt_ast[0] == 'error':
                continue # Saltar la evaluación de sentencias que ya tienen errores semánticos
            last_result = evaluate_ast(stmt_ast, current_symbol_table)
        return last_result

    return None # Manejo de nodos no reconocidos o valores nulos

# --- Función para generar el gráfico del AST usando Graphviz ---
# Para simplificar, la usaremos directamente en gramatica.py
# Pero podrías moverla a un archivo separado si se vuelve muy compleja.
def generate_ast_graph(ast_node):
    dot = graphviz.Digraph(comment='Abstract Syntax Tree', format='png', graph_attr={'rankdir': 'TB'})
    node_counter = 0

    def add_nodes_edges(node, parent_id=None):
        nonlocal node_counter
        current_id = str(node_counter)
        node_counter += 1

        if isinstance(node, tuple):
            node_type = node[0]
            label = str(node_type)
            if node_type == 'number' or node_type == 'id':
                label += f"({node[1]})"
            dot.node(current_id, label=label)

            if parent_id:
                dot.edge(parent_id, current_id)

            # Recursivamente añadir hijos
            for child in node[1:]:
                # Ignorar si el hijo es None, útil para nodos de error o nodos incompletos
                if child is not None:
                    add_nodes_edges(child, current_id)
        elif isinstance(node, list):
            # Para listas de sentencias (como el 'program' o 'block')
            # Simplificamos conectando sentencias directamente al padre que las contiene.
            # Solo si el padre existe y tiene un atributo 'label' (es un nodo ya creado en graphviz)
            if parent_id and current_id in dot.body and 'label' in dot.node(parent_id).attr: # Check if parent_id refers to an existing node with label attribute
                parent_label = dot.node(parent_id).attr['label']
                # Si el padre es un tipo de nodo que contiene una lista de sentencias directamente
                if parent_label in ["program", "Statements", "if", "if_else", "while"]:
                    for child_stmt in node:
                        if child_stmt is not None:
                            add_nodes_edges(child_stmt, parent_id)
                else: # Si es una lista que no está contenida lógicamente, crea un nodo 'Statements'
                    dot.node(current_id, label="Statements", shape='box', style='dashed')
                    if parent_id:
                        dot.edge(parent_id, current_id)
                    for child_stmt in node:
                        if child_stmt is not None:
                            add_nodes_edges(child_stmt, current_id)
            elif not parent_id: # Es la raíz del AST y es una lista (program)
                # Crea un nodo "Program" implícito para la raíz si es una lista
                dot.node(current_id, label="Program", shape='box', style='filled', fillcolor='lightblue')
                for child_stmt in node:
                    if child_stmt is not None:
                        add_nodes_edges(child_stmt, current_id)
            else:
                # Caso excepcional si una lista aparece sin un padre válido y no es la raíz.
                # Podríamos crear un nodo de "Lista Desconocida" o simplemente no procesarlo.
                pass
        
    add_nodes_edges(ast_node)
    return dot

def parse_and_interpret_code(code):
    lexer.reset_lexical_errors()
    reset_syntactic_errors()
    reset_semantic_errors()
    reset_symbol_table()
    ast = parser.parse(code, lexer=lexer.lexer)
    all_errors = lexer.get_lexical_errors() + get_syntactic_errors() + get_semantic_errors()
    evaluated_results = {}
    if not all_errors:
        try:
            evaluate_ast(ast, symbol_table) 
            for var_name, var_info in symbol_table.items():
                if var_info['evaluated_value'] is not None:
                    evaluated_results[var_name] = var_info['evaluated_value']
        except Exception as e:
            add_semantic_error(f"Error interno durante la ejecución: {e}", None, None)
        all_errors = lexer.get_lexical_errors() + get_syntactic_errors() + get_semantic_errors()
    return ast, all_errors, evaluated_results

if __name__ == '__main__':
    print("--- Prueba WHILE simple ---")
    code1 = """
    contador = 0
    WHILE (contador < 3) {
        contador = contador + 1
        resultado_while = contador * 10
    }
    """
    ast1, errors1, results1 = parse_and_interpret_code(code1)
    if not errors1:
        print("Sintaxis correcta. AST (parcial):", ast1)
        print("Tabla de símbolos después de la prueba 1:", get_symbol_table())
        print("Resultados Evaluados:", results1)
        if ast1:
            dot_graph = generate_ast_graph(ast1)
            dot_graph.render('ast_output_while', view=True, cleanup=True)
    else:
        print("Errores detectados:")
        for err in errors1:
            print(f"- {err['type']}: {err['message']} (Línea: {err.get('line', 'N/A')}, Columna: {err.get('column', 'N/A')})")
    print("\n")

    print("--- Prueba IF/ELSE y Operadores ---")
    code_if_else = """
    a = 15
    b = 10
    IF (a > b AND NOT (a == b)) {
        resultado = a + 5
    } ELSE {
        resultado = b - 5
    }
    """
    ast_if_else, errors_if_else, results_if_else = parse_and_interpret_code(code_if_else)
    if not errors_if_else:
        print("Sintaxis correcta. AST (parcial):", ast_if_else)
        print("Tabla de símbolos después de la prueba IF/ELSE:", get_symbol_table())
        print("Resultados Evaluados:", results_if_else)
        if ast_if_else:
            dot_graph = generate_ast_graph(ast_if_else)
            dot_graph.render('ast_output_if_else', view=True, cleanup=True)
    else:
        print("Errores detectados:")
        for err in errors_if_else:
            print(f"- {err['type']}: {err['message']} (Línea: {err.get('line', 'N/A')}, Columna: {err.get('column', 'N/A')})")
    print("\n")