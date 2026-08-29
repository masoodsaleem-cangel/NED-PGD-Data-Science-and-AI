"""
The Three Dimensions of Computation
Interactive Streamlit research sandbox

Model:
    X(t) = [S(t), C(t), M(t)]
    E(t) = S(t) * C(t) * M(t)          # abstract effective capability
    D_M(t) = M_n(t) / (S_n(t) + C_n(t)) # normalized dominance ratio

Important:
The supplied research draft explicitly describes E(t)=S*C*M as a starting
point for experimentation, not a claimed physical law. The feasibility
classifier below is therefore an OPERATIONAL EXPERIMENTAL DEFINITION:
a problem is feasible when E(t) >= required computational demand.
This threshold is configurable in the UI.
"""

import io
import math
import time
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Optional ML dependency. The app still works without sklearn.
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.svm import SVC
    from sklearn.naive_bayes import GaussianNB
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, confusion_matrix
    )
    from sklearn.model_selection import train_test_split
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


st.set_page_config(
    page_title="Three Dimensions of Computation",
    page_icon="∿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
.metric-card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 12px;
    padding: 14px;
}
.small {font-size: .85rem; opacity: .75;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Core mathematics
# ---------------------------------------------------------------------

SCENARIOS = {
    "Hardware Dominant": {
        "description": "Speed and capacity grow substantially faster than M.",
        "rS": 0.080, "rC": 0.070, "rM": 0.025,
        "maturation": 0.0,
    },
    "Balanced Development": {
        "description": "Hardware and algorithmic progress remain comparable.",
        "rS": 0.055, "rC": 0.050, "rM": 0.052,
        "maturation": 0.0,
    },
    "Algorithmic Dominance": {
        "description": "M grows sufficiently rapidly to compensate for physical limits.",
        "rS": 0.030, "rC": 0.025, "rM": 0.095,
        "maturation": 0.0,
    },
    "Mathematical Saturation": {
        "description": "M approaches a limiting value while physical dimensions continue growing.",
        "rS": 0.050, "rC": 0.045, "rM": 0.090,
        "maturation": 0.030,
    },
}


@dataclass
class Params:
    horizon: int = 100
    S0: float = 1.0
    C0: float = 1.0
    M0: float = 1.0
    rS: float = 0.05
    rC: float = 0.05
    rM: float = 0.05
    saturation: bool = False
    Mmax: float = 100.0
    noise: float = 0.02
    seed: int = 42
    demand_base: float = 1.0
    demand_growth: float = 0.045
    demand_noise: float = 0.10
    feasibility_threshold: float = 1.0


def simulate(params: Params) -> pd.DataFrame:
    rng = np.random.default_rng(params.seed)
    t = np.arange(params.horizon + 1, dtype=float)

    S = params.S0 * np.exp(params.rS * t)
    C = params.C0 * np.exp(params.rC * t)

    if params.saturation:
        # Logistic-style saturation for M.
        raw = params.M0 * np.exp(params.rM * t)
        M = params.Mmax * raw / (params.Mmax + raw - params.M0)
    else:
        M = params.M0 * np.exp(params.rM * t)

    if params.noise > 0:
        S *= np.exp(rng.normal(0, params.noise, len(t)))
        C *= np.exp(rng.normal(0, params.noise, len(t)))
        M *= np.exp(rng.normal(0, params.noise, len(t)))

    # Abstract effective capability proposed in the research draft.
    E = S * C * M

    # Synthetic computational demand. This is deliberately configurable.
    demand = params.demand_base * np.exp(params.demand_growth * t)
    if params.demand_noise > 0:
        demand *= np.exp(rng.normal(0, params.demand_noise, len(t)))

    feasible = E >= params.feasibility_threshold * demand

    # Normalized variables.
    Sn = S / S[0]
    Cn = C / C[0]
    Mn = M / M[0]

    # Normalized dominance ratio from the research draft.
    DM = Mn / np.maximum(Sn + Cn, 1e-12)

    # Simple physical-vs-algorithmic growth comparison.
    dlogS = np.gradient(np.log(np.maximum(S, 1e-300)), t)
    dlogC = np.gradient(np.log(np.maximum(C, 1e-300)), t)
    dlogM = np.gradient(np.log(np.maximum(M, 1e-300)), t)
    hardware_growth = (dlogS + dlogC) / 2
    algorithmic_growth = dlogM

    df = pd.DataFrame({
        "t": t.astype(int),
        "S": S,
        "C": C,
        "M": M,
        "E": E,
        "Demand": demand,
        "Feasible": feasible.astype(int),
        "S_n": Sn,
        "C_n": Cn,
        "M_n": Mn,
        "D_M": DM,
        "Hardware_Growth": hardware_growth,
        "Algorithmic_Growth": algorithmic_growth,
    })
    return df


def make_ml_data(df: pd.DataFrame, n_samples: int, seed: int, threshold: float,
                 interaction_strength: float = 0.35) -> pd.DataFrame:
    """Create a controlled synthetic ML experiment over the 3 dimensions.

    The target is intentionally generated from the same operational
    feasibility concept, with a configurable nonlinear interaction.
    """
    rng = np.random.default_rng(seed)

    # Sample log-space so all dimensions span meaningful orders of magnitude.
    S = np.exp(rng.uniform(-2.0, 5.0, n_samples))
    C = np.exp(rng.uniform(-2.0, 5.0, n_samples))
    M = np.exp(rng.uniform(-2.0, 5.0, n_samples))

    logE = np.log(S) + np.log(C) + np.log(M)
    interaction = interaction_strength * (
        np.log(S) * np.log(M) +
        np.log(C) * np.log(M)
    ) / 2.0

    score = logE + interaction + rng.normal(0, 0.8, n_samples)
    y = (score >= math.log(max(threshold, 1e-9))).astype(int)

    return pd.DataFrame({
        "Speed_S": S,
        "Capacity_C": C,
        "Algorithmic_M": M,
        "log_S": np.log(S),
        "log_C": np.log(C),
        "log_M": np.log(M),
        "Feasible": y,
    })


def train_ml_models(df_ml, model_names, test_size=0.25):
    features = ["Speed_S", "Capacity_C", "Algorithmic_M"]
    X, y = df_ml[features], df_ml["Feasible"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    models = {
        "Logistic Regression": LogisticRegression(max_iter=2000),
        "Decision Tree": DecisionTreeClassifier(max_depth=8, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=250, max_depth=10, random_state=42, n_jobs=-1),
        "KNN": KNeighborsClassifier(n_neighbors=9),
        "SVM": SVC(probability=True, random_state=42),
        "Naive Bayes": GaussianNB(),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, learning_rate=0.05, random_state=42),
        "Neural Network": MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=1000, early_stopping=True, random_state=42),
    }

    results = {}
    for name in model_names:
        model = models[name]
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        prob = model.predict_proba(X_test)[:, 1]
        results[name] = {
            "model": model,
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "f1": f1_score(y_test, pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, prob),
            "cm": confusion_matrix(y_test, pred),
            "y_test": y_test,
            "prob": prob,
        }
    return results, features


def native_feature_importance(model, features):
    if hasattr(model, "feature_importances_"):
        values = model.feature_importances_
    elif hasattr(model, "coef_"):
        values = np.abs(model.coef_[0])
    else:
        return None
    return pd.DataFrame({"Feature": features, "Importance": values})


def roc_frame(results):
    from sklearn.metrics import roc_curve
    rows = []
    for name, r in results.items():
        fpr, tpr, _ = roc_curve(r["y_test"], r["prob"])
        rows += [{"Model": name, "FPR": x, "TPR": y} for x, y in zip(fpr, tpr)]
    return pd.DataFrame(rows)


def pr_frame(results):
    from sklearn.metrics import precision_recall_curve
    rows = []
    for name, r in results.items():
        precision, recall, _ = precision_recall_curve(r["y_test"], r["prob"])
        rows += [{"Model": name, "Recall": x, "Precision": y} for x, y in zip(recall, precision)]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

st.sidebar.title("Experiment Controls")
st.sidebar.caption("Interactive research sandbox for the three-dimensional model.")

scenario = st.sidebar.selectbox(
    "Synthetic world",
    list(SCENARIOS.keys()),
    index=1,
)
preset = SCENARIOS[scenario]
st.sidebar.info(preset["description"])

st.sidebar.subheader("Time")
horizon = st.sidebar.slider("Time horizon", 10, 500, 100, 10)

st.sidebar.subheader("Initial state")
S0 = st.sidebar.number_input("S₀ — Speed", min_value=0.01, value=1.0, step=0.1)
C0 = st.sidebar.number_input("C₀ — Capacity", min_value=0.01, value=1.0, step=0.1)
M0 = st.sidebar.number_input("M₀ — Algorithmic Capability", min_value=0.01, value=1.0, step=0.1)

st.sidebar.subheader("Growth rates")
rS = st.sidebar.slider("rS — Speed growth", 0.0, 0.20, float(preset["rS"]), 0.005)
rC = st.sidebar.slider("rC — Capacity growth", 0.0, 0.20, float(preset["rC"]), 0.005)
rM = st.sidebar.slider("rM — Algorithmic growth", 0.0, 0.30, float(preset["rM"]), 0.005)

saturation = st.sidebar.checkbox(
    "Saturate M(t)",
    value=(scenario == "Mathematical Saturation"),
)
Mmax = st.sidebar.number_input(
    "M maximum (if saturated)",
    min_value=1.0, value=100.0, step=10.0,
)

st.sidebar.subheader("Synthetic demand")
demand_base = st.sidebar.number_input("Initial demand", min_value=0.01, value=1.0, step=0.1)
demand_growth = st.sidebar.slider("Demand growth", 0.0, 0.20, 0.045, 0.005)
feas_threshold = st.sidebar.number_input(
    "Feasibility multiplier",
    min_value=0.01, value=1.0, step=0.1,
)

st.sidebar.subheader("Noise / reproducibility")
noise = st.sidebar.slider("Dimension noise", 0.0, 0.20, 0.02, 0.01)
demand_noise = st.sidebar.slider("Demand noise", 0.0, 0.50, 0.10, 0.01)
seed = st.sidebar.number_input("Random seed", min_value=0, value=42, step=1)

run = st.sidebar.button("▶ Run Experiment", type="primary", use_container_width=True)

# Always compute a current experiment so controls remain interactive.
params = Params(
    horizon=horizon,
    S0=S0, C0=C0, M0=M0,
    rS=rS, rC=rC, rM=rM,
    saturation=saturation,
    Mmax=Mmax,
    noise=noise,
    seed=int(seed),
    demand_base=demand_base,
    demand_growth=demand_growth,
    demand_noise=demand_noise,
    feasibility_threshold=feas_threshold,
)

if run:
    st.session_state["last_run"] = time.time()

df = simulate(params)


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------

st.title("The Three Dimensions of Computation")
st.markdown(
    "**Speed (S)** · **Capacity (C)** · **Mathematical/Algorithmic Capability (M)**"
)
st.caption(
    "Exploratory Machine Learning project by Muhammad Masood Saleem. "
    "The three-dimensional model is a conceptual framework tested initially with synthetic data."
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Dashboard", "3D Computational Space", "Algorithmic Leverage",
    "Machine Learning", "Data / Export", "Research Paper"
])


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

with tab1:
    latest = df.iloc[-1]
    first = df.iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("S(t)", f"{latest.S:,.3g}")
    c2.metric("C(t)", f"{latest.C:,.3g}")
    c3.metric("M(t)", f"{latest.M:,.3g}")
    c4.metric("E(t) = S×C×M", f"{latest.E:,.3g}")
    c5.metric("Feasibility", "YES" if latest.Feasible else "NO")

    st.subheader("Growth of the three dimensions")

    plot_df = df[["t", "S", "C", "M"]].melt(
        id_vars="t", var_name="Dimension", value_name="Value"
    )
    fig = px.line(
        plot_df, x="t", y="Value", color="Dimension",
        log_y=True,
        title="Three-dimensional computational trajectory (log scale)",
    )
    fig.update_layout(height=470, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Effective capability vs computational demand")
    compare = df[["t", "E", "Demand"]].melt(
        id_vars="t", var_name="Series", value_name="Value"
    )
    fig2 = px.line(compare, x="t", y="Value", color="Series",
                   log_y=True, title="E(t) versus synthetic demand")
    fig2.add_hline(
        y=feas_threshold,
        line_dash="dash",
        annotation_text="Feasibility multiplier",
    )
    st.plotly_chart(fig2, use_container_width=True)

    feasible_pct = 100 * df["Feasible"].mean()
    first_feasible = df.loc[df["Feasible"] == 1, "t"]
    st.info(
        f"Feasible time points: **{feasible_pct:.1f}%**. "
        + (
            f"First feasible point in this run: **t={int(first_feasible.iloc[0])}**."
            if len(first_feasible)
            else "No feasible point occurred in this run."
        )
    )


# ---------------------------------------------------------------------
# 3D computational space
# ---------------------------------------------------------------------

with tab2:
    st.subheader("Three-Dimensional Computational Space")
    st.write("X(t) = [S(t), C(t), M(t)]")

    fig3 = go.Figure()

    fig3.add_trace(go.Scatter3d(
        x=df["S"], y=df["C"], z=df["M"],
        mode="lines+markers",
        marker=dict(
            size=4,
            color=df["t"],
            colorscale="Viridis",
            colorbar=dict(title="t"),
        ),
        line=dict(width=4),
        text=[f"t={x}" for x in df["t"]],
        hovertemplate="S=%{x:.3g}<br>C=%{y:.3g}<br>M=%{z:.3g}<br>%{text}<extra></extra>",
        name="Trajectory",
    ))

    # Mark first and last state.
    fig3.add_trace(go.Scatter3d(
        x=[df["S"].iloc[0], df["S"].iloc[-1]],
        y=[df["C"].iloc[0], df["C"].iloc[-1]],
        z=[df["M"].iloc[0], df["M"].iloc[-1]],
        mode="markers+text",
        marker=dict(size=8),
        text=["Start", "End"],
        textposition="top center",
        name="Endpoints",
    ))

    fig3.update_layout(
        height=650,
        scene=dict(
            xaxis_title="Speed S",
            yaxis_title="Capacity C",
            zaxis_title="Algorithmic Capability M",
            xaxis_type="log",
            yaxis_type="log",
            zaxis_type="log",
        ),
        margin=dict(l=0, r=0, b=0, t=30),
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown(
        "The research draft represents a computational system as a trajectory "
        "through this three-dimensional space."
    )

    st.subheader("Selected state")
    selected_t = st.slider("Select t", 0, horizon, min(horizon, 50))
    row = df.iloc[selected_t]
    a, b, c, d = st.columns(4)
    a.metric("S", f"{row.S:,.4g}")
    b.metric("C", f"{row.C:,.4g}")
    c.metric("M", f"{row.M:,.4g}")
    d.metric("D_M", f"{row.D_M:,.4g}")


# ---------------------------------------------------------------------
# Leverage / dominance
# ---------------------------------------------------------------------

with tab3:
    st.subheader("Mathematical Leverage and Dominance")

    st.markdown(
        "The draft defines normalized variables and proposes "
        "**D_M(t) = M_n(t) / (S_n(t) + C_n(t))**. "
        "A value above 1 classifies M as dominant under that particular "
        "synthetic definition."
    )

    fig4 = px.line(
        df, x="t", y="D_M",
        title="Normalized mathematical dominance ratio D_M(t)"
    )
    fig4.add_hline(y=1, line_dash="dash", annotation_text="D_M = 1")
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Growth-rate comparison")
    growth = df[["t", "Hardware_Growth", "Algorithmic_Growth"]].melt(
        id_vars="t", var_name="Series", value_name="Growth Rate"
    )
    fig5 = px.line(
        growth, x="t", y="Growth Rate", color="Series",
        title="Local growth rates"
    )
    fig5.add_hline(y=0, line_dash="dot")
    st.plotly_chart(fig5, use_container_width=True)

    dominant_fraction = (df["D_M"] > 1).mean()
    alg_growth_dominant = (
        df["Algorithmic_Growth"] > df["Hardware_Growth"]
    ).mean()

    x1, x2 = st.columns(2)
    x1.metric("Fraction with D_M > 1", f"{100*dominant_fraction:.1f}%")
    x2.metric(
        "Fraction M growth > average hardware growth",
        f"{100*alg_growth_dominant:.1f}%"
    )

    st.warning(
        "Do not interpret D_M > 1 as a universal physical claim. "
        "It is a classification rule for this experimental normalization."
    )


# ---------------------------------------------------------------------
# ML experiment
# ---------------------------------------------------------------------

with tab4:
    st.subheader("Machine-Learning Experiment")

    if not SKLEARN_OK:
        st.error("scikit-learn is not installed. Install requirements.txt and restart Streamlit.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            n_samples = st.slider("Synthetic ML samples", 500, 20000, 5000, 500)
        with c2:
            interaction = st.slider("S–M / C–M interaction strength", 0.0, 1.5, 0.35, 0.05)
        with c3:
            test_size = st.slider("Test-set proportion", 0.10, 0.40, 0.25, 0.05)

        available_models = [
            "Logistic Regression", "Decision Tree", "Random Forest", "KNN",
            "SVM", "Naive Bayes", "Gradient Boosting", "Neural Network"
        ]
        selected_models = st.multiselect(
            "Select models to compare", available_models,
            default=["Logistic Regression", "Decision Tree", "Random Forest", "SVM", "Gradient Boosting"]
        )

        ml_df = make_ml_data(
            df, n_samples=n_samples, seed=int(seed),
            threshold=feas_threshold, interaction_strength=interaction
        )
        st.caption(
            f"Synthetic feasibility rate: {100*ml_df['Feasible'].mean():.1f}% "
            f"({int(ml_df['Feasible'].sum()):,}/{len(ml_df):,})"
        )

        if not selected_models:
            st.warning("Select at least one model.")
        elif ml_df["Feasible"].nunique() < 2:
            st.warning("Only one target class was generated. Adjust the experiment controls.")
        else:
            results, features = train_ml_models(ml_df, selected_models, test_size)

            comparison = pd.DataFrame([
                {"Model": name, "Accuracy": r["accuracy"], "Precision": r["precision"],
                 "Recall": r["recall"], "F1": r["f1"], "ROC-AUC": r["roc_auc"]}
                for name, r in results.items()
            ]).sort_values("F1", ascending=False)

            st.markdown("### Model Comparison")
            st.dataframe(comparison.style.format({
                "Accuracy": "{:.3f}", "Precision": "{:.3f}", "Recall": "{:.3f}",
                "F1": "{:.3f}", "ROC-AUC": "{:.3f}"
            }), use_container_width=True)

            metric = st.selectbox("Metric for comparison graph",
                                  ["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"], index=3)
            st.plotly_chart(px.bar(
                comparison.sort_values(metric), x="Model", y=metric,
                title=f"Model Comparison — {metric}", range_y=[0, 1]
            ), use_container_width=True)

            st.markdown("### ROC Curves")
            rdf = roc_frame(results)
            fig_roc = px.line(rdf, x="FPR", y="TPR", color="Model")
            fig_roc.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash"))
            st.plotly_chart(fig_roc, use_container_width=True)

            st.markdown("### Precision–Recall Curves")
            pdf = pr_frame(results)
            st.plotly_chart(px.line(pdf, x="Recall", y="Precision", color="Model"),
                            use_container_width=True)

            st.markdown("### Confusion Matrix")
            cm_model = st.selectbox("Select model", list(results.keys()), key="cm_model")
            cm = results[cm_model]["cm"]
            st.plotly_chart(px.imshow(
                cm, text_auto=True,
                x=["Predicted 0", "Predicted 1"], y=["Actual 0", "Actual 1"],
                title=f"{cm_model} — Confusion Matrix", labels={"color": "Count"}
            ), use_container_width=True)

            st.markdown("### Feature Importance")
            fi_model = st.selectbox("Select model for feature importance",
                                    list(results.keys()), key="fi_model")
            importance = native_feature_importance(results[fi_model]["model"], features)
            if importance is not None:
                st.plotly_chart(px.bar(
                    importance.sort_values("Importance"), x="Importance", y="Feature",
                    orientation="h", title=f"{fi_model} — Feature Importance"
                ), use_container_width=True)
            else:
                st.info("This model does not expose native feature importance.")

            st.markdown("### Computational-Space Graphs")
            graph = st.selectbox("Select graph", [
                "3D S–C–M Classification", "Speed vs Capacity",
                "Speed vs Mathematical Capability", "Capacity vs Mathematical Capability",
                "Correlation Heatmap"
            ])

            plot_df = ml_df.sample(min(5000, len(ml_df)), random_state=int(seed)).copy()
            plot_df["Class"] = plot_df["Feasible"].map({0: "Infeasible", 1: "Feasible"})

            if graph == "3D S–C–M Classification":
                fig = px.scatter_3d(plot_df, x="Speed_S", y="Capacity_C", z="Algorithmic_M",
                                    color="Class", log_x=True, log_y=True, log_z=True,
                                    title="Speed–Capacity–Mathematical Capability Space")
                fig.update_layout(height=700)
            elif graph == "Speed vs Capacity":
                fig = px.scatter(plot_df, x="Speed_S", y="Capacity_C", color="Class",
                                 log_x=True, log_y=True, title="Speed vs Capacity")
            elif graph == "Speed vs Mathematical Capability":
                fig = px.scatter(plot_df, x="Speed_S", y="Algorithmic_M", color="Class",
                                 log_x=True, log_y=True,
                                 title="Speed vs Mathematical/Algorithmic Capability")
            elif graph == "Capacity vs Mathematical Capability":
                fig = px.scatter(plot_df, x="Capacity_C", y="Algorithmic_M", color="Class",
                                 log_x=True, log_y=True,
                                 title="Capacity vs Mathematical/Algorithmic Capability")
            else:
                corr = ml_df[["Speed_S", "Capacity_C", "Algorithmic_M", "Feasible"]].corr()
                fig = px.imshow(corr, text_auto=".2f", title="Correlation Heatmap",
                                labels={"color": "Correlation"})
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Predicted Probability Distribution")
            probability_model = st.selectbox("Select probability model", list(results.keys()),
                                             key="probability_model")
            r = results[probability_model]
            probability_df = pd.DataFrame({
                "Probability": r["prob"],
                "Actual": r["y_test"].map({0: "Infeasible", 1: "Feasible"}).values
            })
            st.plotly_chart(px.histogram(
                probability_df, x="Probability", color="Actual", nbins=30,
                barmode="overlay", title=f"{probability_model} — Predicted Feasibility"
            ), use_container_width=True)

            st.caption(
                "These ML experiments use synthetic observations and test relationships "
                "among Speed, Capacity, and Mathematical/Algorithmic Capability under "
                "the selected simulation assumptions."
            )


# ---------------------------------------------------------------------
# Data / export
# ---------------------------------------------------------------------

with tab5:
    st.subheader("Synthetic Dataset")
    st.dataframe(df, use_container_width=True, height=420)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download experiment CSV",
        data=csv_bytes,
        file_name="three_dimensions_experiment.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.subheader("Current parameter configuration")
    config = pd.DataFrame({
        "Parameter": [
            "Scenario", "Horizon", "S0", "C0", "M0",
            "rS", "rC", "rM", "Saturation", "Mmax",
            "Demand Base", "Demand Growth", "Feasibility Multiplier",
            "Dimension Noise", "Demand Noise", "Seed"
        ],
        "Value": [
            scenario, horizon, S0, C0, M0,
            rS, rC, rM, saturation, Mmax,
            demand_base, demand_growth, feas_threshold,
            noise, demand_noise, seed
        ]
    })
    st.dataframe(config, use_container_width=True)


# ---------------------------------------------------------------------
# Research notes
# ---------------------------------------------------------------------

st.divider()
with st.expander("Research / model notes"):
    st.markdown("""
**Core state**

`X(t) = [S(t), C(t), M(t)]`

**Synthetic growth**

`S(t) = S₀ exp(rS t)`

`C(t) = C₀ exp(rC t)`

`M(t) = M₀ exp(rM t)`

or a bounded logistic-style form when saturation is enabled.

**Effective capability**

`E(t) = S(t) × C(t) × M(t)`

This is treated here as an experimental starting point rather than a
fundamental physical equation.

**Operational feasibility**

`Feasible = 1` when `E(t) >= feasibility_multiplier × Demand(t)`.

The research draft does not specify one final universal feasibility threshold,
so the threshold is exposed as a control rather than hidden in the code.

**Normalized mathematical dominance**

`D_M(t) = M_n(t) / (S_n(t) + C_n(t))`

`D_M > 1` is treated as mathematical/algorithmic dominance under the
document's particular synthetic definition.

The four synthetic worlds represented in the UI are:
hardware dominance, balanced development, algorithmic dominance, and
mathematical saturation.
""")

st.caption(
    "Research prototype — results are synthetic and should not be presented "
    "as empirical evidence until validated against defined real-world measurements."
)


# ---------------------------------------------------------------------
# Research paper — loaded from a separate repository file
# ---------------------------------------------------------------------

with tab6:
    st.subheader("Research Paper")
    st.caption(
        "The paper is stored as a separate HTML file in the repository. "
        "Edit that file and the Streamlit tab will display the updated version."
    )

    research_file = Path(__file__).resolve().parent / "The_Three_Dimensions_of_Computation.htm"

    if research_file.exists():
        try:
            research_html = research_file.read_text(encoding="utf-8")
            components.html(research_html, height=1200, scrolling=True)
        except Exception as exc:
            st.error(f"Unable to load the research paper: {exc}")
    else:
        st.error(
            "Research paper not found. Keep "
            "`The_Three_Dimensions_of_Computation.htm` in the same folder as `app.py`."
        )
