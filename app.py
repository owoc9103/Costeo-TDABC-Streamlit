"""
TDABC - Costeo Basado en Actividades por Tiempo
Version basica: captura manual + 5 fases de calculo
"""
import streamlit as st
import pandas as pd

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
fase1["tasa_costo_min"] = fase1["overhead_mensual"] / fase1["capacidad_practica_min"]

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
fase2["tiempo_tx_min"] = fase2["tiempo_estandar_min"] + fase2["aporte_variables"]

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
fase4["costo_unitario"] = fase4["costo_actividad"] / fase4["volumen_mensual"].replace(0, pd.NA)

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
fase5["pct_ociosidad"] = fase5["cap_no_usada"] / fase5["capacidad_practica_min"]

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