"""
TDABC - Costeo Basado en Actividades por Tiempo
Version basica: captura manual + 5 fases de calculo
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------- Configuracion de pagina ----------
st.set_page_config(page_title="Costeo TDABC", layout="wide")
st.title("Costeo Basado en Actividades por Tiempo (TDABC)")

# ---------- Inicializacion del estado ----------
if "departamentos" not in st.session_state:
    st.session_state.departamentos = pd.DataFrame(
        columns=["id_departamento", "nombre", "overhead_mensual",
                 "n_empleados", "horas_dia", "dias_mes", "pct_improductivo"]
    )

if "actividades" not in st.session_state:
    st.session_state.actividades = pd.DataFrame(
        columns=["id_actividad", "id_departamento", "nombre",
                 "objeto_costo", "tiempo_estandar_min", "volumen_mensual"]
    )

if "variables" not in st.session_state:
    st.session_state.variables = pd.DataFrame(
        columns=["id_actividad", "id_variable", "descripcion",
                 "coeficiente", "valor_xi"]
    )


# ---------- Utilidades ----------
def siguiente_id(df, columna, prefijo):
    """Genera el siguiente ID tipo D1, D2, A1, A2, etc."""
    if df.empty:
        return f"{prefijo}1"
    numeros = df[columna].str.replace(prefijo, "").astype(int)
    return f"{prefijo}{numeros.max() + 1}"


def renumerar_variables(df_variables):
    """Reasigna X1, X2... dentro de cada actividad, en el orden actual de las filas."""
    df = df_variables.copy()
    if not df.empty:
        df["id_variable"] = "X" + (df.groupby("id_actividad").cumcount() + 1).astype(str)
    return df


def eliminar_departamento(id_dep):
    """Elimina un departamento y en cascada sus actividades y variables."""
    acts_a_borrar = st.session_state.actividades.loc[
        st.session_state.actividades["id_departamento"] == id_dep, "id_actividad"
    ].tolist()
    st.session_state.variables = st.session_state.variables[
        ~st.session_state.variables["id_actividad"].isin(acts_a_borrar)
    ].reset_index(drop=True)
    st.session_state.actividades = st.session_state.actividades[
        st.session_state.actividades["id_departamento"] != id_dep
    ].reset_index(drop=True)
    st.session_state.departamentos = st.session_state.departamentos[
        st.session_state.departamentos["id_departamento"] != id_dep
    ].reset_index(drop=True)


def eliminar_actividad(id_act):
    """Elimina una actividad y en cascada sus variables."""
    st.session_state.variables = st.session_state.variables[
        st.session_state.variables["id_actividad"] != id_act
    ].reset_index(drop=True)
    st.session_state.actividades = st.session_state.actividades[
        st.session_state.actividades["id_actividad"] != id_act
    ].reset_index(drop=True)


def eliminar_variable(id_act, id_var):
    """Elimina una variable especifica."""
    mask = ~(
        (st.session_state.variables["id_actividad"] == id_act) &
        (st.session_state.variables["id_variable"] == id_var)
    )
    st.session_state.variables = st.session_state.variables[mask].reset_index(drop=True)


# =====================================================
# MARCO TEORICO
# =====================================================
st.header("Marco teórico")

with st.expander("¿Qué es el costeo TDABC?", expanded=True):
    st.markdown(
        """
        El **Time-Driven Activity-Based Costing (TDABC)**, o *Costeo Basado en Actividades
        por Tiempo*, es una evolución del ABC tradicional propuesta por **Robert Kaplan y
        Steven Anderson (2004)**. Su objetivo es asignar los costos indirectos de una
        organización a los productos, servicios o clientes con base en **el tiempo que
        realmente consumen las actividades operativas**, en lugar de hacerlo a través de
        encuestas subjetivas de porcentaje de dedicación.

        El método se apoya en dos parámetros centrales por cada departamento o recurso:

        1. **Tasa de costo por minuto ($/min):** se obtiene dividiendo el overhead del
           departamento entre su **capacidad práctica** (minutos realmente disponibles
           para producir, descontando tiempos improductivos).
        2. **Ecuaciones de tiempo:** fórmulas lineales que estiman cuántos minutos
           requiere cada transacción de una actividad en función de sus características
           (p. ej. tiempo estándar + coeficientes por variables como complejidad, canal,
           volumen de línea, etc.).

        El costo asignado a una actividad resulta de multiplicar su **tiempo total
        consumido** por la tasa $/min del departamento al que pertenece. La diferencia
        entre la capacidad práctica y el tiempo efectivamente consumido es la
        **capacidad ociosa**, uno de los grandes aportes del TDABC: hace visible el
        costo de la subutilización de recursos.
        """
    )

with st.expander("Flujo de trabajo de la aplicación", expanded=False):
    st.markdown(
        """
        La página está estructurada de forma secuencial, imitando el flujo lógico del
        modelo TDABC:

        - **Fase 0 — Insumos:** captura manual de los tres bloques de información base.
            - *Tabla 1 · Departamentos:* overhead mensual, número de empleados, horas/día,
              días/mes y porcentaje improductivo.
            - *Tabla 2 · Actividades:* actividades asociadas a cada departamento, con su
              tiempo estándar y volumen mensual esperado.
            - *Tabla 3 · Variables de las ecuaciones de tiempo:* coeficientes y valores Xi
              que ajustan el tiempo estándar según la complejidad de cada transacción.
        - **Fase 1 — Capacidad práctica y tasa $/min:** cálculo de la capacidad práctica
          mensual por departamento y su respectiva tasa de costo por minuto.
        - **Fase 2 — Tiempo por transacción:** aplicación de la ecuación de tiempo
          *(tiempo estándar + Σ coeficiente · Xi)* para cada actividad.
        - **Fase 3 — Tiempo total consumido:** multiplicación del tiempo por transacción
          por el volumen mensual.
        - **Fase 4 — Costo por actividad y costo unitario:** valorización del tiempo
          consumido con la tasa $/min y cálculo del costo unitario por transacción.
        - **Fase 5 — Capacidad no utilizada (ociosidad):** cuantificación en minutos y en
          pesos de la capacidad práctica no consumida por las actividades.
        - **Análisis de ineficiencias:** semáforo de ociosidad por departamento, matriz
          costo unitario vs. volumen y descomposición de las ecuaciones de tiempo.
        - **Simulación de escenarios:** comparación de un escenario *Base* contra dos
          alternativos (*A* y *B*) ocultando departamentos, actividades o variables, y
          ajustando overhead, empleados, horas/día y días/mes.
        - **Análisis de sensibilidad:** diagrama de tornado con elasticidades y mapa de
          calor empleados × overhead, para identificar las palancas que más mueven una
          métrica objetivo.
        """
    )

st.divider()

#Creditos
st.markdown(
    """
    <div style="text-align:center; padding:12px 0; color:#6b7280; font-size:0.9rem;">
        <div><strong>Autor:</strong> Martin Bastidas Magaña</div>
        <div>Apoyado por el <strong>Data-lab</strong> · Pontificia Universidad Javeriana Cali</div>
    </div>
    """,
    unsafe_allow_html=True,
)
# =====================================================
# FASE 0 - INSUMOS
# =====================================================
st.header("Fase 0 - Insumos")

# ---------- Tabla 1: Departamentos ----------
st.subheader("Tabla 1: Departamentos")

st.session_state.departamentos = st.data_editor(
    st.session_state.departamentos,
    column_config={
        "id_departamento": st.column_config.TextColumn("ID", disabled=True),
        "nombre": st.column_config.TextColumn("Nombre"),
        "overhead_mensual": st.column_config.NumberColumn("Overhead mensual", min_value=0.0, format="%.2f"),
        "n_empleados": st.column_config.NumberColumn("# Empleados", min_value=1, step=1),
        "horas_dia": st.column_config.NumberColumn("Horas/dia", min_value=1.0, max_value=24.0, step=1.0),
        "dias_mes": st.column_config.NumberColumn("Dias/mes", min_value=1, max_value=31, step=1),
        "pct_improductivo": st.column_config.NumberColumn("% improductivo (0-1)", min_value=0.0, max_value=1.0, step=0.05),
    },
    num_rows="fixed",
    width="stretch",
    hide_index=True,
    key="editor_departamentos",
)

col_dep1, col_dep2 = st.columns(2)
if col_dep1.button("Añadir fila", key="add_dep"):
    nueva_fila = pd.DataFrame([{
        "id_departamento": siguiente_id(st.session_state.departamentos, "id_departamento", "D"),
        "nombre": "",
        "overhead_mensual": 0.0,
        "n_empleados": 1,
        "horas_dia": 8.0,
        "dias_mes": 25,
        "pct_improductivo": 0.0,
    }])
    st.session_state.departamentos = pd.concat(
        [st.session_state.departamentos, nueva_fila], ignore_index=True
    )
    st.rerun()

if col_dep2.button("Eliminar última fila", key="del_dep", disabled=st.session_state.departamentos.empty):
    id_dep = st.session_state.departamentos.iloc[-1]["id_departamento"]
    eliminar_departamento(id_dep)
    st.rerun()

# ---------- Tabla 2: Actividades ----------
st.subheader("Tabla 2: Actividades")

if st.session_state.departamentos.empty:
    st.info("Primero registra al menos un departamento.")
else:
    st.session_state.actividades = st.data_editor(
        st.session_state.actividades,
        column_config={
            "id_actividad": st.column_config.TextColumn("ID", disabled=True),
            "id_departamento": st.column_config.SelectboxColumn(
                "id_departamento",
                options=st.session_state.departamentos["id_departamento"].tolist(),
                required=True,
            ),
            "nombre": st.column_config.TextColumn("Nombre"),
            "objeto_costo": st.column_config.TextColumn("Objeto del costo"),
            "tiempo_estandar_min": st.column_config.NumberColumn("Tiempo estandar (min)", min_value=0.0, step=1.0),
            "volumen_mensual": st.column_config.NumberColumn("Volumen mensual", min_value=0, step=1),
        },
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        key="editor_actividades",
    )

    col_act1, col_act2 = st.columns(2)
    if col_act1.button("Añadir fila", key="add_act"):
        nueva_fila = pd.DataFrame([{
            "id_actividad": siguiente_id(st.session_state.actividades, "id_actividad", "A"),
            "id_departamento": st.session_state.departamentos.iloc[0]["id_departamento"],
            "nombre": "",
            "objeto_costo": "",
            "tiempo_estandar_min": 0.0,
            "volumen_mensual": 0,
        }])
        st.session_state.actividades = pd.concat(
            [st.session_state.actividades, nueva_fila], ignore_index=True
        )
        st.rerun()

    if col_act2.button("Eliminar última fila", key="del_act", disabled=st.session_state.actividades.empty):
        id_act = st.session_state.actividades.iloc[-1]["id_actividad"]
        eliminar_actividad(id_act)
        st.rerun()

# ---------- Tabla 3: Variables de ecuaciones de tiempo ----------
st.subheader("Tabla 3: Variables de las ecuaciones de tiempo")

if st.session_state.actividades.empty:
    st.info("Primero registra al menos una actividad.")
else:
    editado = st.data_editor(
        st.session_state.variables,
        column_config={
            "id_actividad": st.column_config.SelectboxColumn(
                "id_actividad",
                options=st.session_state.actividades["id_actividad"].tolist(),
                required=True,
            ),
            "id_variable": st.column_config.TextColumn("ID", disabled=True),
            "descripcion": st.column_config.TextColumn("Descripcion de la variable"),
            "coeficiente": st.column_config.NumberColumn("Coeficiente (min)", min_value=0.0, step=1.0),
            "valor_xi": st.column_config.NumberColumn("Valor Xi", min_value=0.0, step=1.0),
        },
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        key="editor_variables",
    )
    st.session_state.variables = renumerar_variables(editado)

    col_var1, col_var2 = st.columns(2)
    if col_var1.button("Añadir fila", key="add_var"):
        nueva_fila = pd.DataFrame([{
            "id_actividad": st.session_state.actividades.iloc[0]["id_actividad"],
            "id_variable": "",
            "descripcion": "",
            "coeficiente": 0.0,
            "valor_xi": 1.0,
        }])
        st.session_state.variables = renumerar_variables(
            pd.concat([st.session_state.variables, nueva_fila], ignore_index=True)
        )
        st.rerun()

    if col_var2.button("Eliminar última fila", key="del_var", disabled=st.session_state.variables.empty):
        ultima = st.session_state.variables.iloc[-1]
        eliminar_variable(ultima["id_actividad"], ultima["id_variable"])
        st.rerun()


# =====================================================
# FASES DE CALCULO
# =====================================================
st.divider()
st.header("Resultados del costeo")

deps = st.session_state.departamentos
acts = st.session_state.actividades
vars_ = st.session_state.variables

if deps.empty or acts.empty:
    st.warning("Registra al menos un departamento y una actividad para ver los calculos.")
    st.stop()

# ---------- Fase 1: Capacidad practica y tasa $/min ----------
st.subheader("Fase 1 - Capacidad practica y tasa costo/minuto")

fase1 = deps.copy()
fase1["capacidad_practica_min"] = (
    fase1["n_empleados"] * fase1["horas_dia"] * 60
    * fase1["dias_mes"] * (1 - fase1["pct_improductivo"])
)
fase1["tasa_costo_min"] = fase1.apply(
    lambda r: (r["overhead_mensual"] / r["capacidad_practica_min"])
    if r["capacidad_practica_min"] > 0 else float("nan"),
    axis=1,
)

st.dataframe(
    fase1[["id_departamento", "nombre", "capacidad_practica_min",
           "overhead_mensual", "tasa_costo_min"]]
    .rename(columns={
        "id_departamento": "id_dep",
        "nombre": "Departamento",
        "capacidad_practica_min": "Capacidad practica (min)",
        "overhead_mensual": "Overhead",
        "tasa_costo_min": "Tasa ($/min)",
    })
    .style.format({
        "Capacidad practica (min)": "{:,.0f}",
        "Overhead": "${:,.0f}",
        "Tasa ($/min)": "${:,.2f}",
    }),
    width="stretch", hide_index=True
)

# ---------- Fase 2: Tiempo por transaccion ----------
st.subheader("Fase 2 - Tiempo por transaccion de cada actividad")

# tiempo_tx = tiempo_estandar + sum(coeficiente * valor_xi)
if not vars_.empty:
    aporte_variables = (
        vars_.assign(aporte=vars_["coeficiente"] * vars_["valor_xi"])
        .groupby("id_actividad")["aporte"].sum()
    )
else:
    aporte_variables = pd.Series(dtype=float)

fase2 = acts.copy()
fase2["aporte_variables"] = fase2["id_actividad"].map(aporte_variables).fillna(0)
fase2["tiempo_tx_min"] = fase2["tiempo_estandar_min"].fillna(0) + fase2["aporte_variables"]

st.dataframe(
    fase2[["id_actividad", "nombre", "tiempo_estandar_min",
           "aporte_variables", "tiempo_tx_min"]]
    .rename(columns={
        "id_actividad": "id_act",
        "nombre": "Actividad",
        "tiempo_estandar_min": "T. estandar",
        "aporte_variables": "Aporte variables",
        "tiempo_tx_min": "Tiempo/tx (min)",
    }),
    width="stretch", hide_index=True
)

# ---------- Fase 3: Tiempo total consumido por actividad ----------
st.subheader("Fase 3 - Tiempo consumido total por actividad")

fase3 = fase2.copy()
fase3["tiempo_total_min"] = fase3["tiempo_tx_min"] * fase3["volumen_mensual"]

st.dataframe(
    fase3[["id_actividad", "nombre", "volumen_mensual",
           "tiempo_tx_min", "tiempo_total_min"]]
    .rename(columns={
        "id_actividad": "id_act",
        "nombre": "Actividad",
        "volumen_mensual": "Volumen",
        "tiempo_tx_min": "Tiempo/tx",
        "tiempo_total_min": "Tiempo total (min)",
    })
    .style.format({"Tiempo total (min)": "{:,.0f}"}),
    width="stretch", hide_index=True
)

# ---------- Fase 4: Costo por actividad y costo unitario ----------
st.subheader("Fase 4 - Costo por actividad y costo unitario")

fase4 = fase3.merge(
    fase1[["id_departamento", "tasa_costo_min"]],
    on="id_departamento", how="left"
)
fase4["costo_actividad"] = fase4["tiempo_total_min"] * fase4["tasa_costo_min"]
fase4["costo_unitario"] = fase4.apply(
    lambda r: (r["costo_actividad"] / r["volumen_mensual"])
    if pd.notna(r["volumen_mensual"]) and r["volumen_mensual"] > 0 else float("nan"),
    axis=1,
)

st.dataframe(
    fase4[["id_actividad", "nombre", "id_departamento", "tasa_costo_min",
           "costo_actividad", "volumen_mensual", "costo_unitario"]]
    .rename(columns={
        "id_actividad": "id_act",
        "nombre": "Actividad",
        "id_departamento": "id_dep",
        "tasa_costo_min": "Tasa",
        "costo_actividad": "Costo actividad",
        "volumen_mensual": "Volumen",
        "costo_unitario": "Costo unitario",
    })
    .style.format({
        "Tasa": "${:,.2f}",
        "Costo actividad": "${:,.2f}",
        "Costo unitario": "${:,.2f}",
    }),
    width="stretch", hide_index=True
)

# ---------- Fase 5: Capacidad no utilizada / ociosidad ----------
st.subheader("Fase 5 - Capacidad no utilizada (ociosidad)")

consumo_por_dep = (
    fase3.groupby(
        fase3["id_actividad"].map(acts.set_index("id_actividad")["id_departamento"])
    )["tiempo_total_min"].sum()
)

fase5 = fase1[["id_departamento", "nombre", "capacidad_practica_min", "tasa_costo_min"]].copy()
fase5["min_consumidos"] = fase5["id_departamento"].map(consumo_por_dep).fillna(0)
fase5["cap_no_usada"] = fase5["capacidad_practica_min"] - fase5["min_consumidos"]
fase5["costo_ociosidad"] = fase5["cap_no_usada"] * fase5["tasa_costo_min"]
fase5["pct_ociosidad"] = fase5.apply(
    lambda r: (r["cap_no_usada"] / r["capacidad_practica_min"])
    if r["capacidad_practica_min"] > 0 else float("nan"),
    axis=1,
)

st.dataframe(
    fase5[["id_departamento", "nombre", "capacidad_practica_min",
           "min_consumidos", "cap_no_usada", "costo_ociosidad", "pct_ociosidad"]]
    .rename(columns={
        "id_departamento": "id_dep",
        "nombre": "Departamento",
        "capacidad_practica_min": "Cap. practica",
        "min_consumidos": "Min. consumidos",
        "cap_no_usada": "Cap. no usada",
        "costo_ociosidad": "Costo ociosidad",
        "pct_ociosidad": "% ociosidad",
    })
    .style.format({
        "Cap. practica": "{:,.0f}",
        "Min. consumidos": "{:,.0f}",
        "Cap. no usada": "{:,.0f}",
        "Costo ociosidad": "${:,.2f}",
        "% ociosidad": "{:.1%}",
    }),
    width="stretch", hide_index=True
)


# =====================================================
# ANALISIS DE INEFICIENCIAS
# =====================================================
st.divider()
st.header("Analisis de Ineficiencias")

col_u1, col_u2 = st.columns(2)
umbral_saludable = col_u1.number_input(
    "Umbral Saludable / Atencion (% ociosidad)",
    min_value=0.0, max_value=1.0, value=0.10, step=0.01, format="%.2f",
    key="umbral_saludable",
)
umbral_critico = col_u2.number_input(
    "Umbral Atencion / Critico (% ociosidad)",
    min_value=0.0, max_value=1.0, value=0.25, step=0.01, format="%.2f",
    key="umbral_critico",
)
if umbral_saludable >= umbral_critico:
    st.error("El umbral Saludable/Atencion debe ser menor que el umbral Atencion/Critico.")
    st.stop()

# ---------- 1. Semaforo de ociosidad ----------
st.subheader("Semaforo de ociosidad por departamento")

def clasificar_ociosidad(pct):
    if pct <= umbral_saludable:
        return "Saludable", "#2ecc71"
    if pct <= umbral_critico:
        return "Atencion", "#f1c40f"
    return "Critico", "#e74c3c"

semaforo = fase5[["id_departamento", "nombre", "pct_ociosidad"]].copy()
semaforo[["categoria", "color"]] = semaforo["pct_ociosidad"].apply(
    lambda p: pd.Series(clasificar_ociosidad(p))
)

cols_sem = st.columns(max(1, len(semaforo)))
for col, fila in zip(cols_sem, semaforo.itertuples()):
    col.markdown(
        f"""
        <div style="background-color:{fila.color};padding:16px;border-radius:8px;
                    color:white;text-align:center;">
            <div style="font-size:0.85rem;opacity:0.9;">{fila.id_departamento}</div>
            <div style="font-size:1.1rem;font-weight:bold;">{fila.nombre}</div>
            <div style="font-size:1.8rem;font-weight:bold;margin:4px 0;">
                {fila.pct_ociosidad:.1%}
            </div>
            <div style="font-size:0.95rem;">{fila.categoria}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.dataframe(
    semaforo[["id_departamento", "nombre", "pct_ociosidad", "categoria"]]
    .rename(columns={
        "id_departamento": "id_dep",
        "nombre": "Departamento",
        "pct_ociosidad": "% ociosidad",
        "categoria": "Categoria",
    })
    .style.format({"% ociosidad": "{:.1%}"}),
    width="stretch", hide_index=True,
)

# ---------- 2. Matriz Costo Unitario vs Volumen ----------
st.subheader("Matriz Costo Unitario vs. Volumen")
st.text("Linea vertical: promedio de volumen de todas las actividades")
st.text("Linea Horizontal: Promedio de costo unitario")


matriz = fase4[[
    "id_actividad", "nombre", "id_departamento",
    "volumen_mensual", "costo_unitario", "costo_actividad",
]].copy()
for col in ["volumen_mensual", "costo_unitario", "costo_actividad"]:
    matriz[col] = pd.to_numeric(matriz[col], errors="coerce")
matriz = matriz.dropna(subset=["costo_unitario"])

if matriz.empty or matriz["volumen_mensual"].sum() == 0:
    st.info("No hay datos suficientes para dibujar la matriz (revisa volumenes y costos).")
else:
    prom_vol = matriz["volumen_mensual"].mean()
    prom_costo = matriz["costo_unitario"].mean()

    fig_matriz = px.scatter(
        matriz,
        x="volumen_mensual",
        y="costo_unitario",
        color="id_departamento",
        size="costo_actividad",
        hover_name="nombre",
        hover_data={
            "id_actividad": True,
            "id_departamento": True,
            "volumen_mensual": ":,.0f",
            "costo_unitario": ":,.2f",
            "costo_actividad": ":,.2f",
        },
        labels={
            "volumen_mensual": "Volumen mensual",
            "costo_unitario": "Costo unitario",
            "id_departamento": "Departamento",
        },
    )
    fig_matriz.add_vline(x=prom_vol, line_dash="dash", line_color="gray")
    fig_matriz.add_hline(y=prom_costo, line_dash="dash", line_color="gray")

    x_max = matriz["volumen_mensual"].max()
    y_max = matriz["costo_unitario"].max()
    anotaciones = [
        (prom_vol + (x_max - prom_vol) / 2, prom_costo / 2, "Alto Volumen + Bajo Costo Unitario "),
        (prom_vol + (x_max - prom_vol) / 2, prom_costo + (y_max - prom_costo) / 2, "Alto Volumen + Alto Costo Unitario"),
        (prom_vol / 2, prom_costo + (y_max - prom_costo) / 2, "Bajo Volumen + Alto Costo Unitario"),
        (prom_vol / 2, prom_costo / 2, "Bajo Volumen + Bajo Costo Unitario"),
    ]
    for x, y, texto in anotaciones:
        fig_matriz.add_annotation(
            x=x, y=y, text=texto, showarrow=False,
            font=dict(size=11, color="gray"), opacity=0.7,
        )

    st.plotly_chart(fig_matriz, width="stretch")

# ---------- 3. Descomposicion de la ecuacion de tiempo ----------
st.subheader("Descomposicion de la ecuacion de tiempo por variable")

if vars_.empty:
    st.info("No hay variables registradas para descomponer.")
else:
    tiempo_tx = fase2.set_index("id_actividad")[["nombre", "tiempo_tx_min"]]
    desc = vars_.copy()
    desc["coeficiente"] = pd.to_numeric(desc["coeficiente"], errors="coerce")
    desc["valor_xi"] = pd.to_numeric(desc["valor_xi"], errors="coerce")
    desc["aporte_min"] = desc["coeficiente"] * desc["valor_xi"]
    desc = desc.join(tiempo_tx, on="id_actividad")
    desc["tiempo_tx_min"] = pd.to_numeric(desc["tiempo_tx_min"], errors="coerce")
    desc = desc[desc["tiempo_tx_min"] > 0].copy()
    desc["pct_aporte"] = desc["aporte_min"] / desc["tiempo_tx_min"]

    if desc.empty:
        st.info("Ninguna actividad con variables tiene tiempo por transaccion > 0.")
    else:
        fig_desc = px.bar(
            desc,
            x="aporte_min",
            y="nombre",
            color="descripcion",
            orientation="h",
            hover_data={
                "id_actividad": True,
                "id_variable": True,
                "coeficiente": ":,.2f",
                "valor_xi": ":,.2f",
                "aporte_min": ":,.2f",
                "pct_aporte": ":.1%",
            },
            labels={
                "aporte_min": "Aporte (min)",
                "nombre": "Actividad",
                "descripcion": "Variable",
            },
        )
        fig_desc.update_layout(barmode="stack", legend_title_text="Variable")
        st.plotly_chart(fig_desc, width="stretch")

        st.dataframe(
            desc[["id_actividad", "id_variable", "descripcion", "aporte_min", "pct_aporte"]]
            .rename(columns={
                "id_actividad": "id_act",
                "id_variable": "id_var",
                "descripcion": "Descripcion",
                "aporte_min": "Aporte (min)",
                "pct_aporte": "% aporte",
            })
            .style.format({"Aporte (min)": "{:,.2f}", "% aporte": "{:.1%}"}),
            width="stretch", hide_index=True,
        )


# =====================================================
# SIMULACION DE ESCENARIOS
# =====================================================
st.divider()
st.header("Simulación de escenarios")


sim_escenarios_ids = ["base", "a", "b"]
sim_nombres = {"base": "Base", "a": "Escenario A", "b": "Escenario B"}


def sim_escenario_vacio():
    return {
        "overhead": {},
        "n_empleados": {},
        "horas_dia": {},
        "dias_mes": {},
        "deps_ocultos": set(),
        "acts_ocultas": set(),
        "vars_ocultas": set(),
    }


def sim_sincronizar_estado(sim_deps, sim_acts, sim_vars_df):
    """Sincronizacion aditiva: agrega ids nuevos sin pisar lo que el usuario tocó."""
    for _id_esc in sim_escenarios_ids:
        _clave = f"sim_esc_{_id_esc}"
        if _clave not in st.session_state:
            st.session_state[_clave] = sim_escenario_vacio()
        _esc = st.session_state[_clave]
        for _k in ["overhead", "n_empleados", "horas_dia", "dias_mes"]:
            _esc.setdefault(_k, {})
        for _k in ["deps_ocultos", "acts_ocultas", "vars_ocultas"]:
            _esc.setdefault(_k, set())
        for _, _r in sim_deps.iterrows():
            _idd = _r["id_departamento"]
            if _idd not in _esc["overhead"]:
                _v = _r["overhead_mensual"]
                _esc["overhead"][_idd] = float(_v) if pd.notna(_v) else 0.0
            if _idd not in _esc["n_empleados"]:
                _v = _r["n_empleados"]
                _esc["n_empleados"][_idd] = int(_v) if pd.notna(_v) else 1
            if _idd not in _esc["horas_dia"]:
                _v = _r["horas_dia"]
                _esc["horas_dia"][_idd] = float(_v) if pd.notna(_v) else 8.0
            if _idd not in _esc["dias_mes"]:
                _v = _r["dias_mes"]
                _esc["dias_mes"][_idd] = float(_v) if pd.notna(_v) else 25.0


def sim_calcular(sim_deps_in, sim_acts_in, sim_vars_in, sim_esc):
    """Recalcula las 5 fases sobre copias, aplicando overrides y ocultamientos del escenario."""
    # Copias defensivas
    sim_deps = sim_deps_in.copy()
    sim_acts = sim_acts_in.copy()
    sim_vars_ = sim_vars_in.copy()

    # Tipado numerico
    for _c in ["overhead_mensual", "n_empleados", "horas_dia", "dias_mes", "pct_improductivo"]:
        if _c in sim_deps.columns:
            sim_deps[_c] = pd.to_numeric(sim_deps[_c], errors="coerce")
    for _c in ["tiempo_estandar_min", "volumen_mensual"]:
        if _c in sim_acts.columns:
            sim_acts[_c] = pd.to_numeric(sim_acts[_c], errors="coerce")
    for _c in ["coeficiente", "valor_xi"]:
        if _c in sim_vars_.columns:
            sim_vars_[_c] = pd.to_numeric(sim_vars_[_c], errors="coerce")

    # Overrides por departamento (ignora ids que ya no existen)
    for _idd, _v in sim_esc.get("overhead", {}).items():
        _m = sim_deps["id_departamento"] == _idd
        if _m.any():
            sim_deps.loc[_m, "overhead_mensual"] = float(_v)
    for _idd, _v in sim_esc.get("n_empleados", {}).items():
        _m = sim_deps["id_departamento"] == _idd
        if _m.any():
            sim_deps.loc[_m, "n_empleados"] = float(_v)
    for _idd, _v in sim_esc.get("horas_dia", {}).items():
        _m = sim_deps["id_departamento"] == _idd
        if _m.any():
            sim_deps.loc[_m, "horas_dia"] = float(_v)
    for _idd, _v in sim_esc.get("dias_mes", {}).items():
        _m = sim_deps["id_departamento"] == _idd
        if _m.any():
            sim_deps.loc[_m, "dias_mes"] = float(_v)

    # Ocultamientos (vars_ocultas usa claves compuestas "id_act::id_var")
    _deps_oc = set(sim_esc.get("deps_ocultos", set()))
    _acts_oc = set(sim_esc.get("acts_ocultas", set()))
    _vars_oc = set(sim_esc.get("vars_ocultas", set()))
    sim_deps = sim_deps[~sim_deps["id_departamento"].isin(_deps_oc)].reset_index(drop=True)
    sim_acts = sim_acts[~sim_acts["id_departamento"].isin(_deps_oc)].reset_index(drop=True)
    sim_acts = sim_acts[~sim_acts["id_actividad"].isin(_acts_oc)].reset_index(drop=True)
    sim_vars_ = sim_vars_[sim_vars_["id_actividad"].isin(sim_acts["id_actividad"])].reset_index(drop=True)
    if not sim_vars_.empty:
        _clave_var = sim_vars_["id_actividad"].astype(str) + "::" + sim_vars_["id_variable"].astype(str)
        sim_vars_ = sim_vars_[~_clave_var.isin(_vars_oc)].reset_index(drop=True)

    # Fase 1
    sim_f1 = sim_deps.copy()
    sim_f1["capacidad_practica_min"] = (
        sim_f1["n_empleados"].fillna(0) * sim_f1["horas_dia"].fillna(0) * 60
        * sim_f1["dias_mes"].fillna(0) * (1 - sim_f1["pct_improductivo"].fillna(0))
    )
    sim_f1["tasa_costo_min"] = sim_f1.apply(
        lambda r: (r["overhead_mensual"] / r["capacidad_practica_min"])
        if r["capacidad_practica_min"] > 0 else float("nan"),
        axis=1,
    )

    # Variables activas con aporte (coef * xi)
    sim_vars_activas = sim_vars_.copy()
    if not sim_vars_activas.empty:
        sim_vars_activas["aporte_min"] = (
            sim_vars_activas["coeficiente"].fillna(0) * sim_vars_activas["valor_xi"].fillna(0)
        )
        _aporte = sim_vars_activas.groupby("id_actividad")["aporte_min"].sum()
    else:
        sim_vars_activas["aporte_min"] = pd.Series(dtype=float)
        _aporte = pd.Series(dtype=float)

    # Fase 2
    sim_f2 = sim_acts.copy()
    sim_f2["aporte_variables"] = sim_f2["id_actividad"].map(_aporte).fillna(0)
    sim_f2["tiempo_tx_min"] = sim_f2["tiempo_estandar_min"].fillna(0) + sim_f2["aporte_variables"]

    # Fase 3
    sim_f3 = sim_f2.copy()
    sim_f3["tiempo_total_min"] = sim_f3["tiempo_tx_min"] * sim_f3["volumen_mensual"].fillna(0)

    # Fase 4
    sim_f4 = sim_f3.merge(
        sim_f1[["id_departamento", "tasa_costo_min"]], on="id_departamento", how="left"
    )
    sim_f4["costo_actividad"] = sim_f4["tiempo_total_min"] * sim_f4["tasa_costo_min"]
    sim_f4["costo_unitario"] = sim_f4.apply(
        lambda r: (r["costo_actividad"] / r["volumen_mensual"])
        if pd.notna(r["volumen_mensual"]) and r["volumen_mensual"] > 0 else float("nan"),
        axis=1,
    )

    # Fase 5
    if not sim_f3.empty:
        _cons = sim_f3.groupby("id_departamento")["tiempo_total_min"].sum()
    else:
        _cons = pd.Series(dtype=float)
    sim_f5 = sim_f1[["id_departamento", "nombre", "capacidad_practica_min",
                     "tasa_costo_min", "overhead_mensual"]].copy()
    sim_f5["min_consumidos"] = sim_f5["id_departamento"].map(_cons).fillna(0)
    sim_f5["cap_no_usada"] = sim_f5["capacidad_practica_min"] - sim_f5["min_consumidos"]
    sim_f5["costo_ociosidad"] = sim_f5["cap_no_usada"] * sim_f5["tasa_costo_min"]
    sim_f5["pct_ociosidad"] = sim_f5.apply(
        lambda r: (r["cap_no_usada"] / r["capacidad_practica_min"])
        if r["capacidad_practica_min"] > 0 else float("nan"),
        axis=1,
    )

    def _sim_cat(r):
        if not (r["capacidad_practica_min"] > 0):
            return "Capacidad inválida"
        if r["cap_no_usada"] < 0:
            return "Sobrecargado"
        return "Normal"
    sim_f5["categoria"] = sim_f5.apply(_sim_cat, axis=1)

    # KPI
    _oh = float(sim_deps["overhead_mensual"].fillna(0).sum()) if not sim_deps.empty else 0.0
    _ca = float(sim_f4["costo_actividad"].fillna(0).sum()) if not sim_f4.empty else 0.0
    _co = float(sim_f5["costo_ociosidad"].fillna(0).sum()) if not sim_f5.empty else 0.0
    _mc = float(sim_f5["min_consumidos"].sum()) if not sim_f5.empty else 0.0
    _cap = float(sim_f5["capacidad_practica_min"].sum()) if not sim_f5.empty else 0.0
    _pg = ((_cap - _mc) / _cap) if _cap > 0 else float("nan")
    _ns = int((sim_f5["categoria"] == "Sobrecargado").sum()) if not sim_f5.empty else 0

    return {
        "fase1": sim_f1, "fase2": sim_f2, "fase3": sim_f3,
        "fase4": sim_f4, "fase5": sim_f5,
        "variables": sim_vars_activas,
        "kpi": {
            "overhead_considerado": _oh,
            "costo_asignado": _ca,
            "costo_ociosidad": _co,
            "minutos_consumidos": _mc,
            "capacidad_total": _cap,
            "pct_ociosidad_global": _pg,
            "n_sobrecargados": _ns,
        },
    }


def sim_render_escenario(sim_id_esc, sim_deps, sim_acts, sim_vars_df):
    """UI de un escenario individual."""
    _clave = f"sim_esc_{sim_id_esc}"
    _esc = st.session_state[_clave]

    # Bloque 1: Ocultamientos
    st.markdown("**Ocultamientos**")
    _co1, _co2, _co3 = st.columns(3)
    _deps_ids = sim_deps["id_departamento"].tolist()
    _sel_d = _co1.multiselect(
        "Departamentos a ocultar",
        options=_deps_ids,
        default=[d for d in _esc["deps_ocultos"] if d in _deps_ids],
        format_func=lambda d: f"{d} - {sim_deps.loc[sim_deps['id_departamento']==d, 'nombre'].iloc[0]}",
        key=f"sim_ms_deps_{sim_id_esc}",
    )
    _esc["deps_ocultos"] = set(_sel_d)

    _acts_visibles = sim_acts[~sim_acts["id_departamento"].isin(_esc["deps_ocultos"])]
    _acts_ids = _acts_visibles["id_actividad"].tolist()
    _sel_a = _co2.multiselect(
        "Actividades a ocultar",
        options=_acts_ids,
        default=[a for a in _esc["acts_ocultas"] if a in _acts_ids],
        format_func=lambda a: f"{a} - {sim_acts.loc[sim_acts['id_actividad']==a, 'nombre'].iloc[0]}",
        key=f"sim_ms_acts_{sim_id_esc}",
    )
    _esc["acts_ocultas"] = set(_sel_a)

    _acts_visibles_2 = _acts_visibles[~_acts_visibles["id_actividad"].isin(_esc["acts_ocultas"])]
    _vars_visibles = sim_vars_df[sim_vars_df["id_actividad"].isin(_acts_visibles_2["id_actividad"])]
    _var_labels = {}
    for _, _rv in _vars_visibles.iterrows():
        _k = f"{_rv['id_actividad']}::{_rv['id_variable']}"
        _var_labels[_k] = f"{_rv['id_actividad']}·{_rv['id_variable']} - {_rv['descripcion']}"
    _var_keys = list(_var_labels.keys())
    _sel_v = _co3.multiselect(
        "Variables a ocultar",
        options=_var_keys,
        default=[k for k in _esc["vars_ocultas"] if k in _var_keys],
        format_func=lambda k: _var_labels[k],
        key=f"sim_ms_vars_{sim_id_esc}",
    )
    _esc["vars_ocultas"] = set(_sel_v)

    # Bloque 2: Ajustes por departamento
    with st.expander("Ajustes por departamento", expanded=False):
        _deps_activos = sim_deps[~sim_deps["id_departamento"].isin(_esc["deps_ocultos"])]
        if _deps_activos.empty:
            st.info("No hay departamentos activos en este escenario.")
        for _, _row in _deps_activos.iterrows():
            _idd = _row["id_departamento"]
            st.caption(f"{_idd} · {_row['nombre']}")
            _cc1, _cc2, _cc3, _cc4 = st.columns(4)
            _val_oh = float(_esc["overhead"].get(_idd, float(_row["overhead_mensual"]) if pd.notna(_row["overhead_mensual"]) else 0.0))
            _esc["overhead"][_idd] = _cc1.number_input(
                "Overhead mensual", value=_val_oh,
                min_value=0.0, step=100000.0, format="%.2f",
                key=f"sim_esc_{sim_id_esc}_overhead_{_idd}",
            )
            _val_ne = int(_esc["n_empleados"].get(_idd, int(_row["n_empleados"]) if pd.notna(_row["n_empleados"]) else 1))
            _esc["n_empleados"][_idd] = _cc2.number_input(
                "# empleados", value=_val_ne,
                min_value=0, step=1,
                key=f"sim_esc_{sim_id_esc}_emp_{_idd}",
            )
            _val_hd = float(_esc["horas_dia"].get(_idd, float(_row["horas_dia"]) if pd.notna(_row["horas_dia"]) else 8.0))
            _esc["horas_dia"][_idd] = _cc3.number_input(
                "Horas/día", value=_val_hd,
                min_value=0.0, max_value=24.0, step=0.5, format="%.2f",
                key=f"sim_esc_{sim_id_esc}_hd_{_idd}",
            )
            _val_dm = float(_esc["dias_mes"].get(_idd, float(_row["dias_mes"]) if pd.notna(_row["dias_mes"]) else 25.0))
            _esc["dias_mes"][_idd] = _cc4.number_input(
                "Días/mes", value=_val_dm,
                min_value=0.0, max_value=31.0, step=1.0, format="%.2f",
                key=f"sim_esc_{sim_id_esc}_dm_{_idd}",
            )

    # Bloque 3: Boton copiar base
    if sim_id_esc in ("a", "b"):
        if st.button("Copiar Base a este escenario", key=f"sim_cpbase_{sim_id_esc}"):
            _base = st.session_state["sim_esc_base"]
            st.session_state[_clave] = {
                "overhead": dict(_base.get("overhead", {})),
                "n_empleados": dict(_base.get("n_empleados", {})),
                "horas_dia": dict(_base.get("horas_dia", {})),
                "dias_mes": dict(_base.get("dias_mes", {})),
                "deps_ocultos": set(_base.get("deps_ocultos", set())),
                "acts_ocultas": set(_base.get("acts_ocultas", set())),
                "vars_ocultas": set(_base.get("vars_ocultas", set())),
            }
            # Limpiar las claves de los widgets de este escenario para que
            # relean los valores recien copiados desde Base en el proximo render.
            _prefijos_num = (
                f"sim_esc_{sim_id_esc}_overhead_",
                f"sim_esc_{sim_id_esc}_emp_",
                f"sim_esc_{sim_id_esc}_hd_",
                f"sim_esc_{sim_id_esc}_dm_",
            )
            _claves_ms = {
                f"sim_ms_deps_{sim_id_esc}",
                f"sim_ms_acts_{sim_id_esc}",
                f"sim_ms_vars_{sim_id_esc}",
            }
            for _k in list(st.session_state.keys()):
                if _k in _claves_ms or any(_k.startswith(_p) for _p in _prefijos_num):
                    del st.session_state[_k]
            st.rerun()

    # Bloque 4: Resultados del escenario
    _res = sim_calcular(sim_deps, sim_acts, sim_vars_df, _esc)
    _kpi = _res["kpi"]

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Overhead considerado", f"${_kpi['overhead_considerado']:,.2f}")
    _m2.metric("Costo asignado", f"${_kpi['costo_asignado']:,.2f}")
    _m3.metric("Costo de ociosidad", f"${_kpi['costo_ociosidad']:,.2f}")
    _m4.metric(
        "% ociosidad global",
        f"{_kpi['pct_ociosidad_global']:.1%}" if pd.notna(_kpi["pct_ociosidad_global"]) else "—",
    )

    st.subheader("Departamentos")
    _tab_dep = _res["fase5"][[
        "id_departamento", "nombre", "capacidad_practica_min", "min_consumidos",
        "cap_no_usada", "pct_ociosidad", "costo_ociosidad", "categoria",
    ]].rename(columns={
        "id_departamento": "id_dep",
        "nombre": "Departamento",
        "capacidad_practica_min": "Capacidad (min)",
        "min_consumidos": "Consumo (min)",
        "cap_no_usada": "Ociosidad (min)",
        "pct_ociosidad": "% ociosidad",
        "costo_ociosidad": "Costo ociosidad",
        "categoria": "Categoría",
    })
    st.dataframe(
        _tab_dep.style.format({
            "Capacidad (min)": "{:,.0f}",
            "Consumo (min)": "{:,.0f}",
            "Ociosidad (min)": "{:,.0f}",
            "% ociosidad": "{:.1%}",
            "Costo ociosidad": "${:,.2f}",
        }, na_rep="—"),
        width="stretch", hide_index=True,
    )

    st.subheader("Actividades")
    _tab_act = _res["fase4"][[
        "id_actividad", "nombre", "id_departamento", "tiempo_tx_min",
        "volumen_mensual", "tiempo_total_min", "costo_actividad", "costo_unitario",
    ]].rename(columns={
        "id_actividad": "id_act",
        "nombre": "Actividad",
        "id_departamento": "id_dep",
        "tiempo_tx_min": "Tiempo/tx (min)",
        "volumen_mensual": "Volumen",
        "tiempo_total_min": "Tiempo total (min)",
        "costo_actividad": "Costo actividad",
        "costo_unitario": "Costo unitario",
    })
    st.dataframe(
        _tab_act.style.format({
            "Tiempo/tx (min)": "{:,.2f}",
            "Volumen": "{:,.0f}",
            "Tiempo total (min)": "{:,.0f}",
            "Costo actividad": "${:,.2f}",
            "Costo unitario": "${:,.2f}",
        }, na_rep="—"),
        width="stretch", hide_index=True,
    )

    st.subheader("Variables")
    _vars_act = _res["variables"]
    if _vars_act.empty:
        st.info("No hay variables activas en este escenario.")
    else:
        _tab_var = _vars_act[[
            "id_actividad", "id_variable", "descripcion",
            "coeficiente", "valor_xi", "aporte_min",
        ]].copy()
        _ttx_map = _res["fase2"].set_index("id_actividad")["tiempo_tx_min"]
        _tab_var["% del t/tx"] = _tab_var.apply(
            lambda r: (r["aporte_min"] / _ttx_map[r["id_actividad"]])
            if r["id_actividad"] in _ttx_map.index and _ttx_map[r["id_actividad"]] > 0
            else float("nan"),
            axis=1,
        )
        _tab_var = _tab_var.rename(columns={
            "id_actividad": "id_act",
            "id_variable": "id_var",
            "descripcion": "Descripción",
            "coeficiente": "Coeficiente (min)",
            "valor_xi": "Valor Xi",
            "aporte_min": "Aporte (min)",
        })
        st.dataframe(
            _tab_var.style.format({
                "Coeficiente (min)": "{:,.2f}",
                "Valor Xi": "{:,.2f}",
                "Aporte (min)": "{:,.2f}",
                "% del t/tx": "{:.1%}",
            }, na_rep="—"),
            width="stretch", hide_index=True,
        )

    # Avisos: 100% ocioso y sobrecargado
    for _, _rd in _res["fase5"].iterrows():
        _idd = _rd["id_departamento"]
        _tiene = (_res["fase4"]["id_departamento"] == _idd).any()
        if not _tiene:
            st.warning(f"{_idd} - {_rd['nombre']} queda 100% ocioso en este escenario.")
    _sob = _res["fase5"][_res["fase5"]["categoria"] == "Sobrecargado"]
    for _, _rs in _sob.iterrows():
        st.warning(f"{_rs['id_departamento']} - {_rs['nombre']} está sobrecargado (consumo > capacidad).")


def sim_render_comparar(sim_deps, sim_acts, sim_vars_df):
    """Tabla comparativa con los tres escenarios lado a lado."""
    _resultados = {
        _i: sim_calcular(sim_deps, sim_acts, sim_vars_df, st.session_state[f"sim_esc_{_i}"])
        for _i in sim_escenarios_ids
    }

    st.subheader("KPI globales")
    _kpi_rows = [
        ("Overhead considerado", "overhead_considerado", "${:,.2f}"),
        ("Costo asignado", "costo_asignado", "${:,.2f}"),
        ("Costo de ociosidad", "costo_ociosidad", "${:,.2f}"),
        ("% ociosidad global", "pct_ociosidad_global", "{:.1%}"),
        ("Minutos consumidos", "minutos_consumidos", "{:,.0f}"),
        ("Capacidad total", "capacidad_total", "{:,.0f}"),
        ("Departamentos sobrecargados", "n_sobrecargados", "{:,.0f}"),
    ]
    _kpi_tabla = []
    for _label, _key, _fmt in _kpi_rows:
        _fila = {"Métrica": _label}
        for _i in sim_escenarios_ids:
            _v = _resultados[_i]["kpi"][_key]
            _fila[sim_nombres[_i]] = _fmt.format(_v) if pd.notna(_v) else "—"
        _kpi_tabla.append(_fila)
    st.dataframe(pd.DataFrame(_kpi_tabla), width="stretch", hide_index=True)

    st.subheader("Por departamento")
    _ids_dep_all = set()
    _nombres_dep = {}
    for _i in sim_escenarios_ids:
        for _, _r in _resultados[_i]["fase5"].iterrows():
            _ids_dep_all.add(_r["id_departamento"])
            _nombres_dep.setdefault(_r["id_departamento"], _r["nombre"])
    _rows_dep = []
    for _idd in sorted(_ids_dep_all):
        _fila = {"id_dep": _idd, "Departamento": _nombres_dep.get(_idd, "")}
        for _i in sim_escenarios_ids:
            _f5 = _resultados[_i]["fase5"].set_index("id_departamento")
            if _idd in _f5.index:
                _cap = _f5.loc[_idd, "capacidad_practica_min"]
                _cons = _f5.loc[_idd, "min_consumidos"]
                _pct = _f5.loc[_idd, "pct_ociosidad"]
                _cost = _f5.loc[_idd, "costo_ociosidad"]
                _fila[f"Cap ({sim_nombres[_i]})"] = f"{_cap:,.0f}" if pd.notna(_cap) else "—"
                _fila[f"Cons ({sim_nombres[_i]})"] = f"{_cons:,.0f}" if pd.notna(_cons) else "—"
                _fila[f"% oc ({sim_nombres[_i]})"] = f"{_pct:.1%}" if pd.notna(_pct) else "—"
                _fila[f"$ oc ({sim_nombres[_i]})"] = f"${_cost:,.2f}" if pd.notna(_cost) else "—"
            else:
                _fila[f"Cap ({sim_nombres[_i]})"] = "—"
                _fila[f"Cons ({sim_nombres[_i]})"] = "—"
                _fila[f"% oc ({sim_nombres[_i]})"] = "—"
                _fila[f"$ oc ({sim_nombres[_i]})"] = "—"
        _rows_dep.append(_fila)
    if _rows_dep:
        st.dataframe(pd.DataFrame(_rows_dep), width="stretch", hide_index=True)
    else:
        st.info("Sin departamentos visibles en ningún escenario.")

    st.subheader("Por actividad")
    _ids_act_all = set()
    _nombres_act = {}
    for _i in sim_escenarios_ids:
        for _, _r in _resultados[_i]["fase4"].iterrows():
            _ids_act_all.add(_r["id_actividad"])
            _nombres_act.setdefault(_r["id_actividad"], _r["nombre"])
    _rows_act = []
    for _ida in sorted(_ids_act_all):
        _fila = {"id_act": _ida, "Actividad": _nombres_act.get(_ida, "")}
        for _i in sim_escenarios_ids:
            _f4 = _resultados[_i]["fase4"].set_index("id_actividad")
            if _ida in _f4.index:
                _ttx = _f4.loc[_ida, "tiempo_tx_min"]
                _cact = _f4.loc[_ida, "costo_actividad"]
                _cu = _f4.loc[_ida, "costo_unitario"]
                _fila[f"t/tx ({sim_nombres[_i]})"] = f"{_ttx:,.2f}" if pd.notna(_ttx) else "—"
                _fila[f"$ act ({sim_nombres[_i]})"] = f"${_cact:,.2f}" if pd.notna(_cact) else "—"
                _fila[f"$ u ({sim_nombres[_i]})"] = f"${_cu:,.2f}" if pd.notna(_cu) else "—"
            else:
                _fila[f"t/tx ({sim_nombres[_i]})"] = "—"
                _fila[f"$ act ({sim_nombres[_i]})"] = "—"
                _fila[f"$ u ({sim_nombres[_i]})"] = "—"
        _rows_act.append(_fila)
    if _rows_act:
        st.dataframe(pd.DataFrame(_rows_act), width="stretch", hide_index=True)
    else:
        st.info("Sin actividades visibles en ningún escenario.")

    st.subheader("Por variable")
    _claves_var_all = set()
    _info_var = {}
    for _i in sim_escenarios_ids:
        _vdf = _resultados[_i]["variables"]
        for _, _rv in _vdf.iterrows():
            _clv = (_rv["id_actividad"], _rv["id_variable"])
            _claves_var_all.add(_clv)
            _info_var.setdefault(_clv, _rv.get("descripcion", ""))
    _rows_var = []
    for _clv in sorted(_claves_var_all):
        _fila = {
            "id_act": _clv[0],
            "id_var": _clv[1],
            "Descripción": _info_var.get(_clv, ""),
        }
        for _i in sim_escenarios_ids:
            _vdf = _resultados[_i]["variables"]
            _sel = _vdf[(_vdf["id_actividad"] == _clv[0]) & (_vdf["id_variable"] == _clv[1])]
            if not _sel.empty:
                _rr = _sel.iloc[0]
                _coef = _rr["coeficiente"]
                _xi = _rr["valor_xi"]
                _ap = _rr["aporte_min"]
                _fila[f"Coef ({sim_nombres[_i]})"] = f"{_coef:,.2f}" if pd.notna(_coef) else "—"
                _fila[f"Xi ({sim_nombres[_i]})"] = f"{_xi:,.2f}" if pd.notna(_xi) else "—"
                _fila[f"Aporte ({sim_nombres[_i]})"] = f"{_ap:,.2f}" if pd.notna(_ap) else "—"
            else:
                _fila[f"Coef ({sim_nombres[_i]})"] = "—"
                _fila[f"Xi ({sim_nombres[_i]})"] = "—"
                _fila[f"Aporte ({sim_nombres[_i]})"] = "—"
        _rows_var.append(_fila)
    if _rows_var:
        st.dataframe(pd.DataFrame(_rows_var), width="stretch", hide_index=True)
    else:
        st.info("Sin variables visibles en ningún escenario.")


def sim_main():
    _deps = st.session_state.departamentos
    _acts = st.session_state.actividades
    _vars_df = st.session_state.variables
    if _deps.empty or _acts.empty:
        st.info("Captura departamentos y actividades para habilitar la simulación.")
        return
    try:
        sim_sincronizar_estado(_deps, _acts, _vars_df)
        _t_base, _t_a, _t_b, _t_cmp = st.tabs(
            [sim_nombres["base"], sim_nombres["a"], sim_nombres["b"], "Comparar"]
        )
        with _t_base:
            sim_render_escenario("base", _deps, _acts, _vars_df)
        with _t_a:
            sim_render_escenario("a", _deps, _acts, _vars_df)
        with _t_b:
            sim_render_escenario("b", _deps, _acts, _vars_df)
        with _t_cmp:
            sim_render_comparar(_deps, _acts, _vars_df)
    except Exception:
        st.error("Ocurrió un error en la sección de simulación.")
        with st.expander("Detalle del error"):
            import traceback as _tb
            st.code(_tb.format_exc())


sim_main()


# =====================================================
# ANALISIS DE SENSIBILIDAD
# =====================================================
st.divider()
st.header("Análisis de sensibilidad")


sens_labels_palancas = {
    "overhead": "Overhead",
    "n_empleados": "Empleados",
    "horas_dia": "Horas/día",
    "dias_mes": "Días/mes",
    "pct_improductivo": "% improductivo",
    "tiempo_estandar": "Tiempo estándar",
    "volumen": "Volumen",
    "coeficiente": "Coeficientes",
}


def sens_metrica(sens_res, sens_met, sens_obj):
    """Extrae una metrica escalar del resultado de sim_calcular."""
    if sens_met == "costo_unitario":
        _f4 = sens_res["fase4"].set_index("id_actividad")
        if sens_obj in _f4.index:
            _v = _f4.loc[sens_obj, "costo_unitario"]
            return float(_v) if pd.notna(_v) else float("nan")
        return float("nan")
    if sens_met == "tasa":
        _f1 = sens_res["fase1"].set_index("id_departamento")
        if sens_obj in _f1.index:
            _v = _f1.loc[sens_obj, "tasa_costo_min"]
            return float(_v) if pd.notna(_v) else float("nan")
        return float("nan")
    if sens_met == "pct_ociosidad":
        _f5 = sens_res["fase5"].set_index("id_departamento")
        if sens_obj in _f5.index:
            _v = _f5.loc[sens_obj, "pct_ociosidad"]
            return float(_v) if pd.notna(_v) else float("nan")
        return float("nan")
    if sens_met == "costo_ociosidad_total":
        return float(sens_res["kpi"]["costo_ociosidad"])
    return float("nan")


def sens_copia_escenario(sens_esc):
    """Copia profunda del escenario (dicts internos y sets)."""
    return {
        "overhead": dict(sens_esc.get("overhead", {})),
        "n_empleados": dict(sens_esc.get("n_empleados", {})),
        "horas_dia": dict(sens_esc.get("horas_dia", {})),
        "dias_mes": dict(sens_esc.get("dias_mes", {})),
        "deps_ocultos": set(sens_esc.get("deps_ocultos", set())),
        "acts_ocultas": set(sens_esc.get("acts_ocultas", set())),
        "vars_ocultas": set(sens_esc.get("vars_ocultas", set())),
    }


def sens_deps_visibles(sens_deps, sens_esc):
    _oc = set(sens_esc.get("deps_ocultos", set()))
    return [d for d in sens_deps["id_departamento"].tolist() if d not in _oc]


def sens_acts_visibles(sens_acts, sens_esc):
    _dep_oc = set(sens_esc.get("deps_ocultos", set()))
    _act_oc = set(sens_esc.get("acts_ocultas", set()))
    return [
        r["id_actividad"] for _, r in sens_acts.iterrows()
        if r["id_departamento"] not in _dep_oc and r["id_actividad"] not in _act_oc
    ]


def sens_aplicar_cambio(sens_deps, sens_acts, sens_vars, sens_esc, sens_cambio):
    """Aplica UN cambio sobre copias del escenario y de los DataFrames.

    Los cambios de overhead / n_empleados / horas_dia / dias_mes van al DICCIONARIO
    del escenario (sim_calcular los aplica desde ahí). Los cambios de pct_improductivo,
    tiempo_estandar, volumen y coeficiente van al DataFrame correspondiente.
    """
    _p = sens_cambio["palanca"]
    _obj = sens_cambio["objetivo"]
    _op = sens_cambio["op"]
    _val = sens_cambio["valor"]

    _deps_vis = sens_deps_visibles(sens_deps, sens_esc)
    _acts_vis = sens_acts_visibles(sens_acts, sens_esc)

    if _p in ("overhead", "n_empleados", "horas_dia", "dias_mes"):
        _objetivos = _deps_vis if _obj == "*" else [_obj]
        for _id in _objetivos:
            if _id not in sens_esc[_p]:
                continue
            _actual = sens_esc[_p][_id]
            if _op == "mult":
                _nuevo = float(_actual) * float(_val)
            else:
                _nuevo = float(_actual) + float(_val)
            # limites
            if _p == "overhead":
                _nuevo = max(0.0, _nuevo)
            elif _p == "n_empleados":
                _nuevo = max(0, int(round(_nuevo)))
            elif _p == "horas_dia":
                _nuevo = max(0.0, min(24.0, _nuevo))
            elif _p == "dias_mes":
                _nuevo = max(0.0, min(31.0, _nuevo))
            sens_esc[_p][_id] = _nuevo

    elif _p == "pct_improductivo":
        _objetivos = _deps_vis if _obj == "*" else [_obj]
        for _id in _objetivos:
            _m = sens_deps["id_departamento"] == _id
            if not _m.any():
                continue
            _actual = pd.to_numeric(sens_deps.loc[_m, "pct_improductivo"], errors="coerce").fillna(0).iloc[0]
            if _op == "mult":
                _nuevo = float(_actual) * float(_val)
            else:
                _nuevo = float(_actual) + float(_val)
            _nuevo = max(0.0, min(0.99, _nuevo))
            sens_deps.loc[_m, "pct_improductivo"] = _nuevo

    elif _p == "tiempo_estandar":
        _objetivos = _acts_vis if _obj == "*" else [_obj]
        for _id in _objetivos:
            _m = sens_acts["id_actividad"] == _id
            if not _m.any():
                continue
            _actual = pd.to_numeric(sens_acts.loc[_m, "tiempo_estandar_min"], errors="coerce").fillna(0).iloc[0]
            if _op == "mult":
                _nuevo = float(_actual) * float(_val)
            else:
                _nuevo = float(_actual) + float(_val)
            _nuevo = max(0.0, _nuevo)
            sens_acts.loc[_m, "tiempo_estandar_min"] = _nuevo

    elif _p == "volumen":
        _objetivos = _acts_vis if _obj == "*" else [_obj]
        for _id in _objetivos:
            _m = sens_acts["id_actividad"] == _id
            if not _m.any():
                continue
            _actual = pd.to_numeric(sens_acts.loc[_m, "volumen_mensual"], errors="coerce").fillna(0).iloc[0]
            if _op == "mult":
                _nuevo = float(_actual) * float(_val)
            else:
                _nuevo = float(_actual) + float(_val)
            _nuevo = max(0.0, _nuevo)
            sens_acts.loc[_m, "volumen_mensual"] = _nuevo

    elif _p == "coeficiente":
        _objetivos = _acts_vis if _obj == "*" else [_obj]
        _vars_oc = set(sens_esc.get("vars_ocultas", set()))
        for _id in _objetivos:
            _m = sens_vars["id_actividad"] == _id
            if not _m.any():
                continue
            if _vars_oc:
                _clv = sens_vars["id_actividad"].astype(str) + "::" + sens_vars["id_variable"].astype(str)
                _m = _m & (~_clv.isin(_vars_oc))
            _actual = pd.to_numeric(sens_vars.loc[_m, "coeficiente"], errors="coerce").fillna(0)
            if _op == "mult":
                _nuevo = _actual * float(_val)
            else:
                _nuevo = _actual + float(_val)
            _nuevo = _nuevo.clip(lower=0.0)
            sens_vars.loc[_m, "coeficiente"] = _nuevo


def sens_evaluar(sens_deps, sens_acts, sens_vars, sens_esc, sens_cambios):
    """Aplica una lista de cambios sobre copias y devuelve el resultado de sim_calcular."""
    _deps = sens_deps.copy()
    _acts = sens_acts.copy()
    _vars = sens_vars.copy()
    # Cast a float para evitar FutureWarnings al asignar valores decimales
    for _c in ["overhead_mensual", "n_empleados", "horas_dia", "dias_mes", "pct_improductivo"]:
        if _c in _deps.columns:
            _deps[_c] = pd.to_numeric(_deps[_c], errors="coerce").astype(float)
    for _c in ["tiempo_estandar_min", "volumen_mensual"]:
        if _c in _acts.columns:
            _acts[_c] = pd.to_numeric(_acts[_c], errors="coerce").astype(float)
    for _c in ["coeficiente", "valor_xi"]:
        if _c in _vars.columns:
            _vars[_c] = pd.to_numeric(_vars[_c], errors="coerce").astype(float)
    _esc = sens_copia_escenario(sens_esc)
    for _c in sens_cambios:
        sens_aplicar_cambio(_deps, _acts, _vars, _esc, _c)
    return sim_calcular(_deps, _acts, _vars, _esc)


def sens_valor_base_dep(sens_deps, sens_esc, sens_id_dep, sens_palanca):
    """Valor base efectivo de una palanca por departamento (después del escenario)."""
    if sens_palanca in ("overhead", "n_empleados", "horas_dia", "dias_mes"):
        if sens_id_dep in sens_esc.get(sens_palanca, {}):
            return float(sens_esc[sens_palanca][sens_id_dep])
        _m = sens_deps["id_departamento"] == sens_id_dep
        if _m.any() and sens_palanca in sens_deps.columns:
            _v = pd.to_numeric(sens_deps.loc[_m, sens_palanca], errors="coerce").fillna(0).iloc[0]
            return float(_v)
    if sens_palanca == "pct_improductivo":
        _m = sens_deps["id_departamento"] == sens_id_dep
        if _m.any():
            _v = pd.to_numeric(sens_deps.loc[_m, "pct_improductivo"], errors="coerce").fillna(0).iloc[0]
            return float(_v)
    return float("nan")


def sens_selector_metrica(sens_deps_vis_df, sens_acts_vis_df, sens_key_prefix):
    """Renderiza selectores de metrica y objeto. Devuelve (metrica, id_obj, label)."""
    _opciones = [
        ("costo_unitario", "Costo unitario (actividad)"),
        ("tasa", "Tasa $/min (departamento)"),
        ("pct_ociosidad", "% ociosidad (departamento)"),
        ("costo_ociosidad_total", "Costo ociosidad total (global)"),
    ]
    _c1, _c2 = st.columns(2)
    _sel = _c1.selectbox(
        "Métrica",
        options=list(range(len(_opciones))),
        format_func=lambda i: _opciones[i][1],
        key=f"{sens_key_prefix}_met",
    )
    _met, _lbl = _opciones[_sel]
    _obj = None
    _lbl_obj = ""
    if _met == "costo_unitario":
        if sens_acts_vis_df.empty:
            _c2.warning("No hay actividades visibles.")
            return _met, None, _lbl
        _ids = sens_acts_vis_df["id_actividad"].tolist()
        _obj = _c2.selectbox(
            "Actividad", options=_ids,
            format_func=lambda a: f"{a} - {sens_acts_vis_df.loc[sens_acts_vis_df['id_actividad']==a, 'nombre'].iloc[0]}",
            key=f"{sens_key_prefix}_obj",
        )
        _lbl_obj = _obj
    elif _met in ("tasa", "pct_ociosidad"):
        if sens_deps_vis_df.empty:
            _c2.warning("No hay departamentos visibles.")
            return _met, None, _lbl
        _ids = sens_deps_vis_df["id_departamento"].tolist()
        _obj = _c2.selectbox(
            "Departamento", options=_ids,
            format_func=lambda d: f"{d} - {sens_deps_vis_df.loc[sens_deps_vis_df['id_departamento']==d, 'nombre'].iloc[0]}",
            key=f"{sens_key_prefix}_obj",
        )
        _lbl_obj = _obj
    return _met, _obj, f"{_lbl}" + (f" · {_lbl_obj}" if _lbl_obj else "")


def sens_formato_metrica(sens_met):
    if sens_met == "pct_ociosidad":
        return "{:.1%}"
    if sens_met in ("costo_unitario", "tasa", "costo_ociosidad_total"):
        return "${:,.2f}"
    return "{:,.2f}"


def sens_render():
    _deps = st.session_state.get("departamentos", pd.DataFrame())
    _acts = st.session_state.get("actividades", pd.DataFrame())
    _vars = st.session_state.get("variables", pd.DataFrame())
    if _deps.empty or _acts.empty:
        st.info("Captura departamentos y actividades para habilitar el análisis de sensibilidad.")
        return

    try:
        # Selector de escenario de partida
        _opciones_esc = []
        for _i in sim_escenarios_ids:
            if f"sim_esc_{_i}" in st.session_state:
                _opciones_esc.append(_i)
        if not _opciones_esc:
            st.info("Primero abre la sección de simulación para inicializar los escenarios.")
            return
        _sel_esc = st.selectbox(
            "Escenario de partida",
            options=_opciones_esc,
            format_func=lambda i: sim_nombres[i],
            key="sens_escenario",
        )
        sens_esc_partida = st.session_state[f"sim_esc_{_sel_esc}"]

        # Universo visible bajo ese escenario
        _dep_oc = set(sens_esc_partida.get("deps_ocultos", set()))
        _act_oc = set(sens_esc_partida.get("acts_ocultas", set()))
        sens_deps_vis = _deps[~_deps["id_departamento"].isin(_dep_oc)].reset_index(drop=True)
        sens_acts_vis = _acts[
            (~_acts["id_departamento"].isin(_dep_oc))
            & (~_acts["id_actividad"].isin(_act_oc))
        ].reset_index(drop=True)

        if sens_deps_vis.empty or sens_acts_vis.empty:
            st.info("El escenario de partida no tiene departamentos o actividades visibles.")
            return

        _tab_tor, _tab_hm = st.tabs(
            ["Tornado y elasticidades", "Mapa de calor"]
        )

        # =============================================
        # HERRAMIENTA 1: TORNADO Y ELASTICIDADES
        # =============================================
        with _tab_tor:
            sens_render_tornado(_deps, _acts, _vars, sens_esc_partida, sens_deps_vis, sens_acts_vis)

        # =============================================
        # HERRAMIENTA 2: MAPA DE CALOR
        # =============================================
        with _tab_hm:
            sens_render_heatmap(_deps, _acts, _vars, sens_esc_partida, sens_deps_vis, sens_acts_vis)

    except Exception:
        st.error("Ocurrió un error en el análisis de sensibilidad.")
        with st.expander("Detalle del error"):
            import traceback as _tb
            st.code(_tb.format_exc())


def sens_render_tornado(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc,
                        sens_deps_vis, sens_acts_vis):
    st.subheader("Tornado y elasticidades")
    _met, _obj, _lbl = sens_selector_metrica(sens_deps_vis, sens_acts_vis, "sens_tor")

    _c1, _c2, _c3, _c4 = st.columns(4)
    sens_shock = _c1.number_input(
        "Shock relativo (± %)", min_value=0.01, max_value=1.0,
        value=0.10, step=0.05, format="%.2f", key="sens_shock",
    )
    sens_shock_pp = _c2.number_input(
        "Shock % improductivo (pp)", min_value=0.01, max_value=0.50,
        value=0.05, step=0.01, format="%.2f", key="sens_shock_pp",
    )
    sens_shock_emp = _c3.number_input(
        "Shock empleados (±)", min_value=1, max_value=10,
        value=1, step=1, key="sens_shock_emp",
    )
    sens_detalle = _c4.selectbox(
        "Nivel de detalle", options=["Agrupado", "Detallado"], key="sens_detalle",
    )
    sens_max_barras = st.number_input(
        "Máximo de barras", min_value=3, max_value=40, value=12, step=1, key="sens_max_barras",
    )

    # Corridas base
    _res_base = sens_evaluar(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc, [])
    _m_base = sens_metrica(_res_base, _met, _obj)

    if pd.isna(_m_base):
        st.warning("La métrica base es NaN; no se puede construir el tornado.")
        return

    # Definir palancas
    _palancas_dep = [
        ("overhead", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
        ("n_empleados", "sum", -sens_shock_emp, +sens_shock_emp, "±{}".format(sens_shock_emp), False),
        ("horas_dia", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
        ("dias_mes", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
        ("pct_improductivo", "sum", -sens_shock_pp, +sens_shock_pp, "±{:.0f} pts".format(sens_shock_pp * 100), False),
    ]
    _palancas_act = [
        ("tiempo_estandar", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
        ("volumen", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
        ("coeficiente", "mult", 1 - sens_shock, 1 + sens_shock, "±{:.0%}".format(sens_shock), True),
    ]

    _filas = []

    def _correr(sens_p, sens_op, sens_vbaja, sens_valta, sens_obj_local):
        _cambio_bajo = [{"palanca": sens_p, "objetivo": sens_obj_local, "op": sens_op, "valor": sens_vbaja}]
        _cambio_alto = [{"palanca": sens_p, "objetivo": sens_obj_local, "op": sens_op, "valor": sens_valta}]
        _r_bajo = sens_evaluar(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc, _cambio_bajo)
        _r_alto = sens_evaluar(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc, _cambio_alto)
        _m_bajo = sens_metrica(_r_bajo, _met, _obj)
        _m_alto = sens_metrica(_r_alto, _met, _obj)
        return _m_bajo, _m_alto

    def _elasticidad(sens_p, sens_op, sens_id_dep, sens_vbaja, sens_valta, _m_bajo, _m_alto):
        if pd.isna(_m_bajo) or pd.isna(_m_alto) or _m_base == 0 or pd.isna(_m_base):
            return float("nan")
        _dm = (_m_alto - _m_bajo) / _m_base
        if sens_op == "mult":
            _dx = sens_valta - sens_vbaja  # (1+s) - (1-s) = 2s
        else:
            if sens_id_dep is None:
                return float("nan")
            _x_base = sens_valor_base_dep(sens_deps_all, sens_esc, sens_id_dep, sens_p)
            if not (_x_base > 0):
                return float("nan")
            _dx = (sens_valta - sens_vbaja) / _x_base
        if _dx == 0:
            return float("nan")
        return _dm / _dx

    if sens_detalle == "Agrupado":
        for _p, _op, _vbaja, _valta, _rango, _tiene_elast in _palancas_dep:
            _objetivos_vis = sens_deps_vis["id_departamento"].tolist()
            if not _objetivos_vis:
                continue
            _m_bajo, _m_alto = _correr(_p, _op, _vbaja, _valta, "*")
            if _op == "mult":
                _elast = _elasticidad(_p, _op, None, _vbaja, _valta, _m_bajo, _m_alto)
            else:
                _elast = float("nan")  # mezcla de deps
            _filas.append({
                "Supuesto": f"{sens_labels_palancas[_p]} (todos)",
                "Palanca": _p, "Rango": _rango,
                "Métrica (bajo)": _m_bajo, "Métrica base": _m_base, "Métrica (alto)": _m_alto,
                "Δ bajo": (_m_bajo - _m_base) if pd.notna(_m_bajo) else float("nan"),
                "Δ alto": (_m_alto - _m_base) if pd.notna(_m_alto) else float("nan"),
                "Elasticidad": _elast,
            })
        for _p, _op, _vbaja, _valta, _rango, _tiene_elast in _palancas_act:
            _objetivos_vis = sens_acts_vis["id_actividad"].tolist()
            if not _objetivos_vis:
                continue
            _m_bajo, _m_alto = _correr(_p, _op, _vbaja, _valta, "*")
            _elast = _elasticidad(_p, _op, None, _vbaja, _valta, _m_bajo, _m_alto) if _op == "mult" else float("nan")
            _filas.append({
                "Supuesto": f"{sens_labels_palancas[_p]} (todas)",
                "Palanca": _p, "Rango": _rango,
                "Métrica (bajo)": _m_bajo, "Métrica base": _m_base, "Métrica (alto)": _m_alto,
                "Δ bajo": (_m_bajo - _m_base) if pd.notna(_m_bajo) else float("nan"),
                "Δ alto": (_m_alto - _m_base) if pd.notna(_m_alto) else float("nan"),
                "Elasticidad": _elast,
            })
    else:
        for _p, _op, _vbaja, _valta, _rango, _tiene_elast in _palancas_dep:
            for _, _rd in sens_deps_vis.iterrows():
                _id_dep = _rd["id_departamento"]
                _m_bajo, _m_alto = _correr(_p, _op, _vbaja, _valta, _id_dep)
                _elast = _elasticidad(_p, _op, _id_dep, _vbaja, _valta, _m_bajo, _m_alto)
                _filas.append({
                    "Supuesto": f"{sens_labels_palancas[_p]} · {_id_dep}",
                    "Palanca": _p, "Rango": _rango,
                    "Métrica (bajo)": _m_bajo, "Métrica base": _m_base, "Métrica (alto)": _m_alto,
                    "Δ bajo": (_m_bajo - _m_base) if pd.notna(_m_bajo) else float("nan"),
                    "Δ alto": (_m_alto - _m_base) if pd.notna(_m_alto) else float("nan"),
                    "Elasticidad": _elast,
                })
        for _p, _op, _vbaja, _valta, _rango, _tiene_elast in _palancas_act:
            for _, _ra in sens_acts_vis.iterrows():
                _id_act = _ra["id_actividad"]
                _m_bajo, _m_alto = _correr(_p, _op, _vbaja, _valta, _id_act)
                _elast = _elasticidad(_p, _op, None, _vbaja, _valta, _m_bajo, _m_alto) if _op == "mult" else float("nan")
                _filas.append({
                    "Supuesto": f"{sens_labels_palancas[_p]} · {_id_act}",
                    "Palanca": _p, "Rango": _rango,
                    "Métrica (bajo)": _m_bajo, "Métrica base": _m_base, "Métrica (alto)": _m_alto,
                    "Δ bajo": (_m_bajo - _m_base) if pd.notna(_m_bajo) else float("nan"),
                    "Δ alto": (_m_alto - _m_base) if pd.notna(_m_alto) else float("nan"),
                    "Elasticidad": _elast,
                })

    if not _filas:
        st.info("Sin palancas evaluables.")
        return

    _df_tor = pd.DataFrame(_filas)
    _df_tor["_absmax"] = _df_tor[["Δ bajo", "Δ alto"]].abs().max(axis=1)
    _df_tor = _df_tor.sort_values("_absmax", ascending=False).head(int(sens_max_barras))
    _df_tor = _df_tor.sort_values("_absmax", ascending=True).reset_index(drop=True)

    # Grafico
    _fmt_m = sens_formato_metrica(_met)
    _fig = go.Figure()
    _fig.add_bar(
        x=_df_tor["Δ bajo"], y=_df_tor["Supuesto"] + " · " + _df_tor["Rango"],
        orientation="h", name="Supuesto baja",
        marker_color="#e74c3c",
        hovertemplate="%{y}<br>Métrica: " + _fmt_m + "<extra></extra>",
        customdata=_df_tor["Métrica (bajo)"],
    )
    _fig.add_bar(
        x=_df_tor["Δ alto"], y=_df_tor["Supuesto"] + " · " + _df_tor["Rango"],
        orientation="h", name="Supuesto sube",
        marker_color="#2ecc71",
        hovertemplate="%{y}<br>Métrica: " + _fmt_m + "<extra></extra>",
        customdata=_df_tor["Métrica (alto)"],
    )
    _titulo_base = f"base = {_fmt_m.format(_m_base)}" if pd.notna(_m_base) else "base = —"
    _fig.update_layout(
        barmode="overlay",
        title=f"Tornado sobre: {_lbl}  ({_titulo_base})",
        xaxis_title=f"Δ frente a la base",
        height=max(320, 30 * len(_df_tor) + 120),
    )
    _fig.add_vline(x=0, line_dash="solid", line_color="gray")
    st.plotly_chart(_fig, width="stretch")
    st.caption("Las barras comparan shocks distintos; revisa la magnitud indicada en cada etiqueta.")

    # Tabla
    _tab = _df_tor[[
        "Supuesto", "Rango", "Métrica (bajo)", "Métrica base",
        "Métrica (alto)", "Δ bajo", "Δ alto", "Elasticidad",
    ]].copy()
    st.dataframe(
        _tab.style.format({
            "Métrica (bajo)": _fmt_m, "Métrica base": _fmt_m, "Métrica (alto)": _fmt_m,
            "Δ bajo": _fmt_m if _met != "pct_ociosidad" else "{:+.1%}",
            "Δ alto": _fmt_m if _met != "pct_ociosidad" else "{:+.1%}",
            "Elasticidad": "{:+.2f}",
        }, na_rep="—"),
        width="stretch", hide_index=True,
    )

    # Nota didactica: volumen y costo unitario / tasa en TDABC
    if _met in ("costo_unitario", "tasa"):
        _vol_row = _df_tor[_df_tor["Palanca"] == "volumen"]
        if not _vol_row.empty:
            _d_bajo = _vol_row["Δ bajo"].abs().max()
            _d_alto = _vol_row["Δ alto"].abs().max()
            if pd.notna(_d_bajo) and pd.notna(_d_alto) and _d_bajo < 1e-9 and _d_alto < 1e-9:
                st.info(
                    "En TDABC el volumen no altera el costo unitario ni la tasa: la tasa depende "
                    "de la capacidad práctica y el costo unitario, del tiempo por transacción de "
                    "la ecuación de tiempo. Lo que sí cambia con el volumen es la ociosidad."
                )


def sens_render_heatmap(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc,
                        sens_deps_vis, sens_acts_vis):
    st.subheader("Mapa de calor: empleados × overhead")

    if sens_deps_vis.empty:
        st.info("No hay departamentos visibles.")
        return

    _c1, _c2 = st.columns([1, 3])
    _sel_dep = _c1.selectbox(
        "Departamento",
        options=sens_deps_vis["id_departamento"].tolist(),
        format_func=lambda d: f"{d} - {sens_deps_vis.loc[sens_deps_vis['id_departamento']==d, 'nombre'].iloc[0]}",
        key="sens_hm_dep",
    )
    _met, _obj, _lbl = sens_selector_metrica(sens_deps_vis, sens_acts_vis, "sens_hm")

    # Valor base de overhead y empleados desde el escenario
    _oh_base = sens_valor_base_dep(sens_deps_all, sens_esc, _sel_dep, "overhead")
    _emp_base = int(sens_valor_base_dep(sens_deps_all, sens_esc, _sel_dep, "n_empleados"))

    _c3, _c4, _c5 = st.columns(3)
    _oh_min = _c3.number_input(
        "Overhead mínimo", min_value=0.0, value=float(_oh_base * 0.70),
        step=100000.0, format="%.2f", key="sens_hm_ohmin",
    )
    _oh_max = _c4.number_input(
        "Overhead máximo", min_value=0.0, value=float(_oh_base * 1.30),
        step=100000.0, format="%.2f", key="sens_hm_ohmax",
    )
    _oh_pasos = _c5.select_slider(
        "Pasos overhead", options=[3, 4, 5, 6, 7, 8, 9], value=5, key="sens_hm_ohpasos",
    )

    _c6, _c7 = st.columns(2)
    _emp_min = _c6.number_input(
        "Empleados mínimo", min_value=1, value=max(1, _emp_base - 2), step=1, key="sens_hm_empmin",
    )
    _emp_max = _c7.number_input(
        "Empleados máximo", min_value=1, value=_emp_base + 2, step=1, key="sens_hm_empmax",
    )
    if _emp_max < _emp_min:
        st.error("Empleados máximo debe ser mayor o igual al mínimo.")
        return
    if _oh_max < _oh_min:
        st.error("Overhead máximo debe ser mayor o igual al mínimo.")
        return

    _emp_vals = list(range(int(_emp_min), int(_emp_max) + 1))
    if len(_emp_vals) > 9:
        _emp_vals = _emp_vals[:9]
    _oh_vals = [_oh_min + (_oh_max - _oh_min) * i / (_oh_pasos - 1) for i in range(int(_oh_pasos))] if _oh_pasos > 1 else [_oh_base]

    _z = [[float("nan")] * len(_oh_vals) for _ in range(len(_emp_vals))]
    _text = [[""] * len(_oh_vals) for _ in range(len(_emp_vals))]
    _cats = [[""] * len(_oh_vals) for _ in range(len(_emp_vals))]
    _fmt_m = sens_formato_metrica(_met)

    for _iy, _emp in enumerate(_emp_vals):
        for _ix, _oh in enumerate(_oh_vals):
            _cambios = [
                {"palanca": "overhead", "objetivo": _sel_dep, "op": "sum", "valor": _oh - sens_valor_base_dep(sens_deps_all, sens_esc, _sel_dep, "overhead")},
                {"palanca": "n_empleados", "objetivo": _sel_dep, "op": "sum", "valor": _emp - int(sens_valor_base_dep(sens_deps_all, sens_esc, _sel_dep, "n_empleados"))},
            ]
            _r = sens_evaluar(sens_deps_all, sens_acts_all, sens_vars_all, sens_esc, _cambios)
            _v = sens_metrica(_r, _met, _obj)
            _z[_iy][_ix] = _v if pd.notna(_v) else None
            _f5 = _r["fase5"].set_index("id_departamento")
            _cat = _f5.loc[_sel_dep, "categoria"] if _sel_dep in _f5.index else ""
            _cats[_iy][_ix] = _cat
            _txt = _fmt_m.format(_v) if pd.notna(_v) else "—"
            if _cat == "Sobrecargado":
                _txt = "⚠ " + _txt
            _text[_iy][_ix] = _txt

    _fig = go.Figure(go.Heatmap(
        z=_z, x=[f"${v:,.0f}" for v in _oh_vals], y=[str(e) for e in _emp_vals],
        text=_text, texttemplate="%{text}",
        colorscale="RdYlGn_r",
        hovertemplate="Overhead: %{x}<br>Empleados: %{y}<br>Métrica: %{text}<extra></extra>",
        colorbar_title=_lbl,
    ))
    # marcar celda base
    if _emp_base in _emp_vals:
        _iy_base = _emp_vals.index(_emp_base)
        # buscar el valor de overhead mas cercano al base
        _ix_base = min(range(len(_oh_vals)), key=lambda i: abs(_oh_vals[i] - _oh_base))
        _fig.add_scatter(
            x=[f"${_oh_vals[_ix_base]:,.0f}"], y=[str(_emp_vals[_iy_base])],
            mode="markers", marker=dict(symbol="square-open", size=40, color="black", line=dict(width=3)),
            name="Base", showlegend=True, hoverinfo="skip",
        )
    _fig.update_layout(
        title=f"{_lbl} — {_sel_dep}",
        xaxis_title="Overhead", yaxis_title="Empleados",
        height=max(350, 60 * len(_emp_vals) + 120),
    )
    st.plotly_chart(_fig, width="stretch")
    st.caption(
        "⚠ capacidad insuficiente para el volumen. El cuadro negro marca la celda base "
        f"({_emp_base} empleados · ${_oh_base:,.0f} de overhead)."
    )
    st.info(
        "Reducir personal solo baja el costo unitario si el overhead baja en la misma "
        "proporción. Si el overhead se mantiene, el costo se redistribuye a las "
        "actividades que quedan."
    )


sens_render()


# =====================================================
# PIE DE PAGINA
# =====================================================

