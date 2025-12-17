import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components
import json
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import io
from pyecharts import options as opts
from pyecharts.charts import Bar, Timeline

# =======================================================
# Carregamento CSS (desativado para testes da aplicação)
# ========================================================
#def load_css():
#    with open(".streamlit/style.css", "r", encoding="utf-8") as f:
#        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

#load_css()


st.set_page_config(page_title="App Controle de Contratos", page_icon="📊", layout="wide")

st.title("📈 Dashboard de Contratos")
st.markdown("Visualize a distribuição de contratos abaixo.")

# ==============================
# Upload da planilha
# ==============================
with st.sidebar:
    st.header("📤 Carregar Planilha")
    upload_file = st.file_uploader(
        "Arraste sua planilha aqui",
        type=["xlsx", "csv", "xls"],
        help="Formatos suportados: Excel (.xlsx, .xls) e CSV (.csv)"
    )


# ==============================
# Função de carregamento
# ==============================
@st.cache_data
def carregar_tabela(arquivo, skiprows=0):
    ext = os.path.splitext(arquivo.name)[1].lower()

    try:
        if ext in [".csv", ".txt"]:
            df = pd.read_csv(arquivo, sep=";", skiprows=skiprows, low_memory=False, decimal=',')
        elif ext in [".xls", ".xlsx", ".xlsm", ".xlsb"]:
            df = pd.read_excel(arquivo, skiprows=skiprows)
        elif ext in [".ods", ".ots"]:
            df = pd.read_excel(arquivo, engine="odf", skiprows=skiprows)
        elif ext in [".xml", ".html"]:
            df = pd.read_html(arquivo)[0]
            if skiprows > 0:
                df = df.iloc[skiprows:].reset_index(drop=True)
        elif ext == ".json":
            df = pd.read_json(arquivo, orient="records")
            if skiprows > 0:
                df = df.iloc[skiprows:].reset_index(drop=True)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {ext}")

        # Limpa nomes de colunas
        df.columns = [str(col).strip() for col in df.columns]

        return df

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None


def converter_datas(df):
    """Converte colunas de data para formato datetime"""
    colunas_data = ['INÍCIO', 'FIM', 'PRICE LIST-VIGÊNCIA']

    for coluna in colunas_data:
        if coluna in df.columns:
            try:
                # Tenta converter para datetime
                df[coluna] = pd.to_datetime(df[coluna], errors='coerce', dayfirst=True)
            except Exception as e:
                st.warning(f"⚠️ Não foi possível converter {coluna}: {e}")

    return df


# ==============================
# Funções para download
# ==============================
def limpar_dataframe_para_download(df):
    """Prepara dataframe para download limpando valores"""
    df_limpo = df.copy()

    # Substitui todos os valores nulos por string vazia
    df_limpo = df_limpo.fillna('')

    # Limpeza em todas as colunas
    for coluna in df_limpo.columns:
        # Converte para string e remove valores indesejados
        df_limpo[coluna] = df_limpo[coluna].astype(str)
        df_limpo[coluna] = df_limpo[coluna].replace(['None', 'nan', 'NaN', 'NaT', '<NA>'], '', regex=True)

        # Formata datas se for datetime no original
        if pd.api.types.is_datetime64_any_dtype(df[coluna]):
            mask = df[coluna].notna()
            df_limpo.loc[mask, coluna] = df.loc[mask, coluna].dt.strftime('%d/%m/%Y')

    return df_limpo


def converter_para_csv(df):
    """Converte DataFrame para CSV"""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig')


def converter_para_excel(df):
    """Converte DataFrame para Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados_Contratos')
    return output.getvalue()


def converter_para_json(df):
    """Converte DataFrame para JSON"""
    return df.to_json(orient='records', indent=2, force_ascii=False)


# ==============================
# Interface principal
# ==============================
if upload_file is not None:
    try:
        # Configuração fixa para pular 4 linhas
        pular_linhas = 4

        # Carrega os dados
        df = carregar_tabela(upload_file, skiprows=pular_linhas)

        if df is None or df.empty:
            st.error("O arquivo está vazio ou não pôde ser processado.")
            st.stop()

        # CONVERTE COLUNAS DE DATA
        df = converter_datas(df)
        df = df.replace([None, ""], np.nan)

        # Mostrar preview dos dados
        st.subheader("👀 Preview dos Dados")
        st.dataframe(df.head(), use_container_width=True)

        # Mostrar informações sobre conversão de datas
        colunas_data = ['INÍCIO', 'FIM', 'PRICE LIST-VIGÊNCIA']
        for coluna in colunas_data:
            if coluna in df.columns and pd.api.types.is_datetime64_any_dtype(df[coluna]):
                dados_validos = df[coluna].notna().sum()
                st.sidebar.success(f"📅 {coluna}: {dados_validos} datas válidas")

        # ==============================
        # FILTROS NO SIDEBAR
        # ==============================
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎛️ Filtros")

        # Mantém a ordem original das colunas, mas remove as específicas
        colunas = df.columns.tolist()

        # Lista de colunas para REMOVER dos filtros
        colunas_remover = ['SALDO', 'PERCENTUAL TEÓRICO', 'PERCENTUAL SEGREGADO']

        # Filtra apenas as colunas que devem aparecer nos filtros
        colunas_filtro = [col for col in colunas if col not in colunas_remover]

         # Inicializa filtros apenas para as colunas que serão mostradas
        if "filtros" not in st.session_state:
            st.session_state["filtros"] = {col: [] for col in colunas_filtro}

        # Botão limpar filtros
        if st.sidebar.button("🧹 Limpar Filtros", use_container_width=True):
            # Limpa todos os filtros das colunas visíveis
            for coluna in colunas_filtro:
                st.session_state[f"multiselect_{coluna}"] = []
            st.session_state["filtros"] = {col: [] for col in colunas_filtro}
            st.rerun()

        # Criação dos filtros interligados (apenas para colunas selecionadas)
        for coluna in colunas_filtro:
            mascara_outras = pd.Series(True, index=df.index)
            for outra_col, escolhas in st.session_state["filtros"].items():
                if outra_col != coluna and escolhas:
                    if pd.api.types.is_datetime64_any_dtype(df[outra_col]):
                        # Para datas, converte as escolhas para datetime
                        datas_escolhidas = [pd.to_datetime(esc) for esc in escolhas]
                        mascara_outras &= df[outra_col].isin(datas_escolhidas)
                    else:
                        mascara_outras &= df[outra_col].astype(str).isin([str(v) for v in escolhas])

            temp_df = df[mascara_outras]

            # Prepara opções baseadas no tipo de dados
            if pd.api.types.is_datetime64_any_dtype(df[coluna]):
                # Para datas, formata bonitinho
                opcoes = sorted(temp_df[coluna].dropna().unique())
                opcoes_str = [d.strftime('%d/%m/%Y') for d in opcoes]
            else:
                opcoes = sorted(temp_df[coluna].dropna().astype(str).unique().tolist())
                opcoes_str = opcoes

            # Usa a chave única para cada multiselect
            escolha = st.sidebar.multiselect(
                f"**{coluna}:**",
                options=opcoes_str,
                default=st.session_state.get(f"multiselect_{coluna}", []),
                key=f"multiselect_{coluna}",
                placeholder=f"Selecione {coluna}..."
            )

            # Atualiza os filtros na session state
            st.session_state["filtros"][coluna] = escolha

        # Aplica filtros combinados
        mascara_final = pd.Series(True, index=df.index)
        for coluna, escolhas in st.session_state["filtros"].items():
            if escolhas:
                if pd.api.types.is_datetime64_any_dtype(df[coluna]):
                    # Para datas, converte de volta para datetime
                    datas_escolhidas = [pd.to_datetime(esc, dayfirst=True) for esc in escolhas]
                    mascara_final &= df[coluna].isin(datas_escolhidas)
                else:
                    mascara_final &= df[coluna].astype(str).isin([str(v) for v in escolhas])

        df_filtrado = df[mascara_final].copy()

        # Mostrar estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📈 Total de Registros", len(df))
        with col2:
            st.metric("✅ Filtrados", len(df_filtrado))
        with col3:
            st.metric("📊 % do Total", f"{(len(df_filtrado) / len(df) * 100):.1f}%" if len(df) > 0 else "0%")

        # ==============================
        # ANÁLISE VISUAL
        # ==============================
        if len(df_filtrado) > 0:
            st.markdown("---")
            st.subheader("📊 Análise Visual")

            # 1. GRÁFICO DE PIZZA - ECHARTS
            if df_filtrado.shape[1] >= 7:
                col_empresa = df_filtrado.columns[1]
                col_valor = df_filtrado.columns[6]

                # Converter valores da coluna 7 para numérico
                df_filtrado[col_valor] = pd.to_numeric(df_filtrado[col_valor], errors='coerce')

                df_grouped = (
                    df_filtrado.groupby(col_empresa)[col_valor]
                    .sum()
                    .reset_index()
                    .sort_values(by=col_valor, ascending=False)
                )

                if not df_grouped.empty:
                    # Prepara os dados para ECharts
                    pie_data = [
                        {"name": str(row[col_empresa]), "value": float(row[col_valor])}
                        for _, row in df_grouped.iterrows()
                    ]

                    chart_data = json.dumps(pie_data)

                    html_pizza = f"""
                    <div id="echart_pizza" class="echarts-container chart-ready" style="width: 100%; height: 400px;"></div>

                    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
                    <script>
                        // Configuração do gráfico de pizza
                        var chartOptions = {{
                            title: {{
                                text: 'Distribuição de {col_valor} por {col_empresa}',
                                left: 'center'
                            }},
                            tooltip: {{
                                trigger: 'item'
                            }},
                            legend: {{
                                orient: 'vertical',
                                left: 'left'
                            }},
                            series: [
                                {{
                                    name: '{col_valor}',
                                    type: 'pie',
                                    radius: ['40%', '70%'],
                                    avoidLabelOverlap: false,
                                    itemStyle: {{
                                        borderRadius: 10,
                                        borderColor: '#fff',
                                        borderWidth: 2
                                    }},
                                    label: {{
                                        show: true,
                                        formatter: '{{b}}: {{d}}%'
                                    }},
                                    emphasis: {{
                                        label: {{
                                            show: true,
                                            fontSize: '16',
                                            fontWeight: 'bold'
                                        }}
                                    }},
                                    labelLine: {{
                                        show: true
                                    }},
                                    data: {chart_data}
                                }}
                            ]
                        }};

                        // Função principal de inicialização
                        function initializeLazyChart() {{
                            console.log('🎯 Inicializando gráfico de pizza com lazy loading...');

                            if (window.initLazyChart) {{
                                var chart = window.initLazyChart('echart_pizza', chartOptions);

                                if (chart) {{
                                    console.log('✅ Gráfico de pizza registrado - animará quando 90% estiver visível');
                                    chart.on('finished', function() {{
                                        document.getElementById('echart_pizza').classList.add('animated');
                                        document.getElementById('echart_pizza').classList.remove('chart-ready');
                                    }});
                                }} else {{
                                    console.warn('⚠️ Falha no lazy loading, usando fallback');
                                    initializeFallback();
                                }}
                            }} else {{
                                console.warn('⚠️ Sistema lazy loading não disponível, usando fallback');
                                initializeFallback();
                            }}
                        }}

                        // Fallback: animação imediata
                        function initializeFallback() {{
                            console.log('🔄 Inicializando fallback (animação imediata)');
                            try {{
                                var chart = echarts.init(document.getElementById('echart_pizza'));
                                chart.setOption({{
                                    ...chartOptions,
                                    animation: true,
                                    animationDuration: 1000,
                                    animationEasing: 'elasticOut'
                                }});

                                // Marca como animado
                                document.getElementById('echart_pizza').classList.add('animated');
                                document.getElementById('echart_pizza').classList.remove('chart-ready');

                                window.addEventListener('resize', function() {{
                                    chart.resize();
                                }});

                            }} catch (error) {{
                                console.error('❌ Erro no fallback:', error);
                            }}
                        }}

                        // Sistema de lazy loading global (se não existir)
                        if (typeof window.initLazyChart === 'undefined') {{
                            window.initLazyChart = function(chartId, options) {{
                                var chartElement = document.getElementById(chartId);
                                if (!chartElement) return null;

                                var chart = echarts.init(chartElement);

                                // Observer para detectar quando o gráfico está 90% visível
                                var observer = new IntersectionObserver(function(entries) {{
                                    entries.forEach(function(entry) {{
                                        if (entry.isIntersecting && entry.intersectionRatio >= 0.9) {{
                                            chart.setOption({{
                                                ...options,
                                                animation: true,
                                                animationDuration: 1000,
                                                animationEasing: 'elasticOut'
                                            }});
                                            observer.unobserve(entry.target);
                                        }}
                                    }});
                                }}, {{ threshold: 0.9 }});

                                observer.observe(chartElement);
                                return chart;
                            }};
                        }}

                        // Estratégias de inicialização
                        if (document.readyState === 'loading') {{
                            document.addEventListener('DOMContentLoaded', initializeLazyChart);
                        }} else {{
                            initializeLazyChart();
                        }}

                        // Backups em caso de falha
                        setTimeout(initializeLazyChart, 500);
                        setTimeout(function() {{
                            var chart = echarts.getInstanceByDom(document.getElementById('echart_pizza'));
                            if (!chart) {{
                                console.log('🔄 Backup: gráfico não inicializado, tentando fallback');
                                initializeFallback();
                            }}
                        }}, 2000);

                        // Backup final - garante que o gráfico será exibido
                        setTimeout(function() {{
                            var chart = echarts.getInstanceByDom(document.getElementById('echart_pizza'));
                            if (!chart) {{
                                console.log('🔄 Último backup: inicialização forçada');
                                initializeFallback();
                            }}
                        }}, 3000);

                    </script>
                    """

                    components.html(html_pizza, height=450)

            # 2. GRÁFICO DE GANTT PARA DATAS DE CONTRATOS
            st.markdown("---")
            st.subheader("📅 Linha do Tempo dos Contratos")

            if len(df_filtrado.columns) >= 4:
                col_inicio = df_filtrado.columns[2]  # Coluna 3
                col_fim = df_filtrado.columns[3]  # Coluna 4
                col_empresa = df_filtrado.columns[1]  # Coluna 2

                if (pd.api.types.is_datetime64_any_dtype(df_filtrado[col_inicio]) and
                        pd.api.types.is_datetime64_any_dtype(df_filtrado[col_fim])):

                    gantt_data = []
                    for idx, row in df_filtrado.iterrows():
                        if pd.notna(row[col_inicio]) and pd.notna(row[col_fim]):
                            gantt_data.append({
                                'Nome': f"{row[col_empresa]} - Contrato {idx}",
                                'Início': row[col_inicio],
                                'Fim': row[col_fim],
                                'Empresa': row[col_empresa],
                                'Duração': (row[col_fim] - row[col_inicio]).days
                            })

                    if gantt_data:
                        df_gantt = pd.DataFrame(gantt_data)

                        fig_gantt = px.timeline(
                            df_gantt,
                            x_start="Início",
                            x_end="Fim",
                            y="Nome",
                            color="Empresa",
                            title="Linha do Tempo dos Contratos",
                            hover_data={"Duração": True, "Empresa": True},
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        fig_gantt.update_yaxes(autorange="reversed")
                        fig_gantt.update_layout(height=400, showlegend=True)
                        st.plotly_chart(fig_gantt, use_container_width=True)

                        # ==============================
                        # AVISO DE CONTRATOS PRÓXIMOS DO VENCIMENTO - VERSÃO COMPACTA
                        # ==============================

                        # Data atual
                        data_atual = pd.Timestamp.now()
                        data_limite = data_atual + pd.DateOffset(years=10)

                        # Filtra contratos
                        contratos_proximos_vencimento = []
                        contratos_vencidos = []

                        for idx, row in df_filtrado.iterrows():
                            if pd.notna(row[col_fim]):
                                if row[col_fim] < data_atual:
                                    contratos_vencidos.append({
                                        'Empresa': row[col_empresa],
                                        'Data_Fim': row[col_fim],
                                        'Dias_Atraso': (data_atual - row[col_fim]).days
                                    })
                                elif row[col_fim] <= data_limite:
                                    dias_para_vencer = (row[col_fim] - data_atual).days
                                    contratos_proximos_vencimento.append({
                                        'Empresa': row[col_empresa],
                                        'Data_Fim': row[col_fim],
                                        'Dias_Para_Vencer': dias_para_vencer
                                    })

                        # MÉTRICAS RÁPIDAS
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "🔴 Vencidos",
                                len(contratos_vencidos),
                                help="Contratos com data de vencimento passada"
                            )

                        with col2:
                            # Conta contratos críticos (até 30 dias)
                            criticos = len([c for c in contratos_proximos_vencimento if c['Dias_Para_Vencer'] <= 30])
                            st.metric(
                                "🟠 Críticos",
                                criticos,
                                help="Vencem em até 30 dias"
                            )

                        with col3:
                            # Total próximos do vencimento
                            st.metric(
                                "🟡 Próximos 10 anos",
                                len(contratos_proximos_vencimento),
                                help="Vencem nos próximos 10 anos"
                            )

                        # ALERTAS EM CONTAINERS EXPANSÍVEIS
                        if contratos_vencidos or contratos_proximos_vencimento:
                            st.markdown("### ⚠️ Alertas de Vencimento")

                            # Contratos Vencidos - Expansível
                            if contratos_vencidos:
                                with st.expander(f"🔴 Contratos Vencidos ({len(contratos_vencidos)})", expanded=False):
                                    df_vencidos = pd.DataFrame(contratos_vencidos)
                                    df_vencidos['Data_Fim'] = df_vencidos['Data_Fim'].dt.strftime('%d/%m/%Y')
                                    df_vencidos = df_vencidos.sort_values('Dias_Atraso', ascending=False)

                                    for i, (_, contrato) in enumerate(df_vencidos.iterrows()):
                                        if i < 5:  # Mostra apenas os 5 primeiros
                                            st.write(f"**{contrato['Empresa']}** - {contrato['Data_Fim']} "
                                                     f"({contrato['Dias_Atraso']} dias atrás)")
                                        elif i == 5:
                                            st.caption(f"... e mais {len(contratos_vencidos) - 5} contratos vencidos")

                            # Contratos Próximos - Expansível
                            if contratos_proximos_vencimento:
                                with st.expander(f"🟡 Próximos do Vencimento ({len(contratos_proximos_vencimento)})",
                                                 expanded=False):
                                    # Agrupa por nível de urgência
                                    criticos = [c for c in contratos_proximos_vencimento if c['Dias_Para_Vencer'] <= 30]
                                    alertas = [c for c in contratos_proximos_vencimento if
                                               30 < c['Dias_Para_Vencer'] <= 90]
                                    atencao = [c for c in contratos_proximos_vencimento if
                                               90 < c['Dias_Para_Vencer'] <= 365]
                                    normais = [c for c in contratos_proximos_vencimento if c['Dias_Para_Vencer'] > 365]

                                    if criticos:
                                        st.write("**🔴 Críticos (até 30 dias):**")
                                        for contrato in sorted(criticos, key=lambda x: x['Dias_Para_Vencer'])[:3]:
                                            data_formatada = contrato['Data_Fim'].strftime('%d/%m/%Y')
                                            st.write(
                                                f"- {contrato['Empresa']} - {data_formatada} ({contrato['Dias_Para_Vencer']} dias)")

                                    if alertas:
                                        st.write("**🟠 Alertas (31-90 dias):**")
                                        for contrato in sorted(alertas, key=lambda x: x['Dias_Para_Vencer'])[:3]:
                                            data_formatada = contrato['Data_Fim'].strftime('%d/%m/%Y')
                                            st.write(
                                                f"- {contrato['Empresa']} - {data_formatada} ({contrato['Dias_Para_Vencer']} dias)")

                                    if atencao:
                                        st.write("**🟡 Atenção (3-12 meses):**")
                                        for contrato in sorted(atencao, key=lambda x: x['Dias_Para_Vencer'])[:3]:
                                            data_formatada = contrato['Data_Fim'].strftime('%d/%m/%Y')
                                            st.write(
                                                f"- {contrato['Empresa']} - {data_formatada} ({contrato['Dias_Para_Vencer']} dias)")

                                    # MOSTRAR CONTRATOS NORMAIS (VERDES) TAMBÉM
                                    if normais:
                                        st.write("**🟢 Normais (acima de 1 ano):**")
                                        # Mostra os 5 mais próximos entre os "normais"
                                        for contrato in sorted(normais, key=lambda x: x['Dias_Para_Vencer'])[:5]:
                                            data_formatada = contrato['Data_Fim'].strftime('%d/%m/%Y')
                                            st.write(
                                                f"- {contrato['Empresa']} - {data_formatada} ({contrato['Dias_Para_Vencer']} dias)")

                                        # Se tiver mais de 5, mostra contador
                                        if len(normais) > 5:
                                            st.caption(
                                                f"... e mais {len(normais) - 5} contratos com vencimento acima de 1 ano")

            # 3. GRÁFICO DE BARRAS ECHARTS (CORRIGIDO COM NOVA LÓGICA)
            st.markdown("---")
            st.subheader("🏢 Comparação: VALOR UTILIZADO vs SALDO RESTANTE")

            # Verifica se as colunas necessárias existem
            colunas_necessarias = ['VALOR GLOBAL', 'SALDO', 'VALOR SEGREGADO',
                                   df_filtrado.columns[1]]  # Coluna 2 é empresa

            if all(col in df_filtrado.columns for col in colunas_necessarias):
                col_global = 'VALOR GLOBAL'  # Coluna F - Valor total do contrato
                col_saldo_restante = 'SALDO'  # Coluna H - Valor que ainda resta
                col_valor_usado = 'VALOR SEGREGADO'  # Coluna G - Valor já utilizado
                col_empresa = df_filtrado.columns[1]  # Coluna 2 (nome das empresas)

                # Converte para numérico
                df_filtrado[col_global] = pd.to_numeric(df_filtrado[col_global], errors='coerce')
                df_filtrado[col_saldo_restante] = pd.to_numeric(df_filtrado[col_saldo_restante], errors='coerce')
                df_filtrado[col_valor_usado] = pd.to_numeric(df_filtrado[col_valor_usado], errors='coerce')

                # Filtra linhas válidas (não nulas)
                mask_validas = (
                        df_filtrado[col_global].notna() &
                        df_filtrado[col_saldo_restante].notna() &
                        df_filtrado[col_valor_usado].notna() &
                        (df_filtrado[col_global] > 0)  # Evita divisão por zero
                )
                df_comparacao = df_filtrado[mask_validas].copy()

                if len(df_comparacao) > 0:
                    # Agrupa por empresa e calcula totais
                    df_empresas = df_comparacao.groupby(col_empresa).agg({
                        col_global: 'sum',
                        col_saldo_restante: 'sum',
                        col_valor_usado: 'sum'
                    }).reset_index()

                    # NOVA LÓGICA: CALCULA PERCENTUAIS CORRETOS
                    df_empresas['percentual_utilizado'] = (df_empresas[col_valor_usado] / df_empresas[col_global]) * 100
                    df_empresas['percentual_restante'] = (df_empresas[col_saldo_restante] / df_empresas[
                        col_global]) * 100

                    # NOVA MÉTRICA DE EFICIÊNCIA: Quanto foi usado do valor total
                    df_empresas['eficiencia'] = (df_empresas[col_valor_usado] / df_empresas[col_global]) * 100

                    # Calcula diferenças (agora faz mais sentido)
                    df_empresas['diferenca_percentual'] = df_empresas['percentual_utilizado'] - df_empresas[
                        'percentual_restante']
                    df_empresas['diferenca_absoluta'] = df_empresas[col_valor_usado] - df_empresas[col_saldo_restante]


                    # LÓGICA DE CLASSIFICAÇÃO BASEADA NA EFICIÊNCIA (uso do contrato)
                    def classificar_status(row):
                        eficiencia = row['eficiencia']  # % do valor total que foi utilizado

                        # Alta eficiência = já usou mais de 70% → URGENTE
                        if eficiencia > 70:
                            return '🚨 URGENTE - RENOVAR IMEDIATO'
                        # Média eficiência = usando entre 30% e 70% → Programar renovação
                        elif eficiencia >= 30:
                            return '🟢 RENOVAR (15 dias)'
                        # Baixa eficiência = pouco uso (menos de 30%) → Avaliar necessidade
                        else:
                            return '🟡 AVALIAR COM CALMA'


                    df_empresas['status'] = df_empresas.apply(classificar_status, axis=1)
                    df_empresas['prioridade'] = df_empresas['status'].map({
                        '🚨 URGENTE - RENOVAR IMEDIATO': 1,
                        '🟢 RENOVAR (15 dias)': 2,
                        '🟡 AVALIAR COM CALMA': 3
                    })

                    # Top 10 empresas por valor global (para o gráfico)
                    df_top = df_empresas.nlargest(10, col_global).copy()

                    # Prepara dados para ECharts (já estão em percentual)
                    empresas = df_top[col_empresa].tolist()
                    utilizado_data = df_top['percentual_utilizado'].round(1).tolist()
                    restante_data = df_top['percentual_restante'].round(1).tolist()

                    #GRÁFICO ECHARTS
                    html_chart = f'''
                    <div id="comparisonChart" class="echarts-container chart-ready" style="width: 100%; height: 500px;"></div>

                    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
                    <script>
                        // Configuração do gráfico
                        var chartOptions = {{
                            tooltip: {{
                                trigger: 'axis',
                                axisPointer: {{
                                    type: 'shadow'
                                }},
                                formatter: function(params) {{
                                    var empresa = params[0].name;
                                    var utilizado = params[0].value;
                                    var restante = params[1].value;
                                    var eficiencia = utilizado.toFixed(1); // Eficiência = % utilizado
                                    var diferenca = (utilizado - restante).toFixed(1);

                                    return `
                                        <div style="padding: 8px;">
                                            <strong>${{empresa}}</strong><br/>
                                            💰 <span style="color: #FF6B00">Valor Total: 100%</span><br/>
                                            ✅ <span style="color: #2196F3">Utilizado: ${{utilizado.toFixed(1)}}%</span><br/>
                                            💰 <span style="color: #4CAF50">Saldo Restante: ${{restante.toFixed(1)}}%</span><br/>
                                            📊 <strong>Eficiência (Uso): ${{eficiencia}}%</strong><br/>
                                            🔄 Diferença: ${{diferenca}}%<br/>
                                        </div>
                                    `;
                                }}
                            }},
                            legend: {{
                                data: ['VALOR UTILIZADO (% do Total)', 'SALDO RESTANTE (% do Total)'],
                                top: 30
                            }},
                            grid: {{
                                left: '3%',
                                right: '4%',
                                bottom: '10%',
                                top: '15%',
                                containLabel: true
                            }},
                            xAxis: {{
                                type: 'category',
                                data: {empresas},
                                axisLabel: {{
                                    rotate: 45,
                                    interval: 0
                                }}
                            }},
                            yAxis: {{
                                type: 'value',
                                min: 0,
                                max: 100,
                                axisLabel: {{
                                    formatter: '{{value}}%'
                                }}
                            }},
                            series: [
                                {{
                                    name: 'VALOR UTILIZADO (% do Total)',
                                    type: 'bar',
                                    data: {utilizado_data},
                                    itemStyle: {{
                                        color: '#2196F3',
                                        borderRadius: [4, 4, 0, 0]
                                    }},
                                    label: {{
                                        show: true,
                                        position: 'top',
                                        formatter: '{{c}}%',
                                        color: '#2196F3',
                                        fontWeight: 'bold'
                                    }}
                                }},
                                {{
                                    name: 'SALDO RESTANTE (% do Total)',
                                    type: 'bar',
                                    data: {restante_data},
                                    itemStyle: {{
                                        color: '#4CAF50',
                                        borderRadius: [4, 4, 0, 0]
                                    }},
                                    label: {{
                                        show: true,
                                        position: 'top',
                                        formatter: '{{c}}%',
                                        color: '#4CAF50',
                                        fontWeight: 'bold'
                                    }}
                                }}
                            ]
                        }};

                        // Função principal de inicialização
                        function initializeLazyChart() {{
                            console.log('🎯 Inicializando gráfico com lazy loading...');

                            if (window.initLazyChart) {{
                                var chart = window.initLazyChart('comparisonChart', chartOptions);

                                if (chart) {{
                                    console.log('✅ Gráfico registrado - animará quando 90% estiver visível');
                                    chart.on('finished', function() {{
                                        document.getElementById('comparisonChart').classList.add('animated');
                                        document.getElementById('comparisonChart').classList.remove('chart-ready');
                                    }});
                                }} else {{
                                    console.warn('⚠️ Falha no lazy loading, usando fallback');
                                    initializeFallback();
                                }}
                            }} else {{
                                console.warn('⚠️ Sistema lazy loading não disponível, usando fallback');
                                initializeFallback();
                            }}
                        }}

                        // Fallback: animação imediata
                        function initializeFallback() {{
                            console.log('🔄 Inicializando fallback (animação imediata)');
                            try {{
                                var chart = echarts.init(document.getElementById('comparisonChart'));
                                chart.setOption({{
                                    ...chartOptions,
                                    animation: true,
                                    animationDuration: 1000,
                                    animationEasing: 'elasticOut'
                                }});

                                // Marca como animado
                                document.getElementById('comparisonChart').classList.add('animated');
                                document.getElementById('comparisonChart').classList.remove('chart-ready');

                                window.addEventListener('resize', function() {{
                                    chart.resize();
                                }});

                            }} catch (error) {{
                                console.error('❌ Erro no fallback:', error);
                            }}
                        }}

                        // Sistema de lazy loading global (se não existir)
                        if (typeof window.initLazyChart === 'undefined') {{
                            window.initLazyChart = function(chartId, options) {{
                                var chartElement = document.getElementById(chartId);
                                if (!chartElement) return null;

                                var chart = echarts.init(chartElement);

                                // Observer para detectar quando o gráfico está 90% visível
                                var observer = new IntersectionObserver(function(entries) {{
                                    entries.forEach(function(entry) {{
                                        if (entry.isIntersecting && entry.intersectionRatio >= 0.9) {{
                                            chart.setOption({{
                                                ...options,
                                                animation: true,
                                                animationDuration: 1000,
                                                animationEasing: 'elasticOut'
                                            }});
                                            observer.unobserve(entry.target);
                                        }}
                                    }});
                                }}, {{ threshold: 0.9 }});

                                observer.observe(chartElement);
                                return chart;
                            }};
                        }}

                        // Estratégias de inicialização
                        if (document.readyState === 'loading') {{
                            document.addEventListener('DOMContentLoaded', initializeLazyChart);
                        }} else {{
                            initializeLazyChart();
                        }}

                        // Backups em caso de falha
                        setTimeout(initializeLazyChart, 500);
                        setTimeout(function() {{
                            var chart = echarts.getInstanceByDom(document.getElementById('comparisonChart'));
                            if (!chart) {{
                                console.log('🔄 Backup: gráfico não inicializado, tentando fallback');
                                initializeFallback();
                            }}
                        }}, 2000);

                        // Backup final - garante que o gráfico será exibido
                        setTimeout(function() {{
                            var chart = echarts.getInstanceByDom(document.getElementById('comparisonChart'));
                            if (!chart) {{
                                console.log('🔄 Último backup: inicialização forçada');
                                initializeFallback();
                            }}
                        }}, 3000);

                    </script>
                    '''

                    components.html(html_chart, height=550)

                    # CONTAINERS EXPANSÍVEIS (ATUALIZADOS COM NOVA LÓGICA)
                    st.markdown("---")
                    st.markdown("### 📋 Status de Renovação por Empresa")

                    # ORDENA POR PRIORIDADE
                    df_empresas = df_empresas.sort_values('prioridade')

                    # Container 1: 🚨 URGENTE - EFICIÊNCIA > 70% (alto uso)
                    df_urgente = df_empresas[df_empresas['status'] == '🚨 URGENTE - RENOVAR IMEDIATO']

                    with st.expander(f"🚨 URGENTE - RENOVAR IMEDIATO ({len(df_urgente)} empresas)", expanded=True):
                        if len(df_urgente) > 0:
                            st.error("**🚨 RENOVAR IMEDIATAMENTE - Contrato com alto uso (>70%)!**")
                            for _, empresa in df_urgente.iterrows():
                                eficiencia = empresa['eficiencia']

                                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 2])
                                with col1:
                                    st.write(f"**{empresa[col_empresa]}**")
                                with col2:
                                    st.metric("Eficiência (Uso)", f"{eficiencia:.1f}%", delta="Alto Uso",
                                              delta_color="normal")
                                with col3:
                                    st.metric("Valor Global", f"R$ {empresa[col_global]:,.0f}")
                                with col4:
                                    st.metric("Utilizado", f"R$ {empresa[col_valor_usado]:,.0f}")
                                with col5:
                                    st.metric("Saldo Restante", f"R$ {empresa[col_saldo_restante]:,.0f}")
                                with col6:
                                    st.error("**RENOVAR JÁ**")

                            st.error(f"⚠️ **{len(df_urgente)} contratos com alto uso - Renovar IMEDIATAMENTE**")
                        else:
                            st.info("ℹ️ Nenhum contrato com uso > 70%")

                    # Container 2: 🟢 RENOVAR - EFICIÊNCIA 30% À 70% (uso moderado)
                    df_renovar = df_empresas[df_empresas['status'] == '🟢 RENOVAR (15 dias)']

                    with st.expander(f"🟢 RENOVAR NO PERÍODO ESTIMADO VIGÊNCIA ({len(df_renovar)} empresas)",
                                     expanded=True):
                        if len(df_renovar) > 0:
                            st.success("**✅ Renovar em até 15 dias - Contrato com uso moderado (30%-70%)**")
                            for _, empresa in df_renovar.iterrows():
                                eficiencia = empresa['eficiencia']
                                diferenca = empresa['diferenca_percentual']

                                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 2])
                                with col1:
                                    st.write(f"**{empresa[col_empresa]}**")
                                with col2:
                                    if eficiencia >= 50:
                                        st.metric("Eficiência (Uso)", f"{eficiencia:.1f}%", delta="Bom Uso",
                                                  delta_color="normal")
                                    else:
                                        st.metric("Eficiência (Uso)", f"{eficiencia:.1f}%", delta="Uso Moderado",
                                                  delta_color="off")
                                with col3:
                                    st.metric("Valor Global", f"R$ {empresa[col_global]:,.0f}")
                                with col4:
                                    st.metric("Utilizado", f"R$ {empresa[col_valor_usado]:,.0f}")
                                with col5:
                                    st.metric("Saldo Restante", f"R$ {empresa[col_saldo_restante]:,.0f}")
                                with col6:
                                    st.metric("Saldo vs Utilizado", f"{diferenca:.1f}%")

                            st.info(f"📅 **{len(df_renovar)} contratos para renovação programada**")
                        else:
                            st.warning("⚠️ Nenhum contrato com uso entre 30% e 70%")

                    # Container 3: 🟡 AVALIAR COM CALMA - EFICIÊNCIA < 30% (pouco uso)
                    df_avaliar = df_empresas[df_empresas['status'] == '🟡 AVALIAR COM CALMA']

                    with st.expander(f"🟡 AVALIAR COM CALMA ({len(df_avaliar)} empresas)", expanded=False):
                        if len(df_avaliar) > 0:
                            st.warning("**🟡 Avaliar com calma - Contrato com baixo uso (<30%)**")
                            for _, empresa in df_avaliar.iterrows():
                                eficiencia = empresa['eficiencia']
                                diferenca = empresa['diferenca_percentual']

                                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 2])
                                with col1:
                                    st.write(f"**{empresa[col_empresa]}**")
                                with col2:
                                    st.metric("Eficiência (Uso)", f"{eficiencia:.1f}%", delta="Baixo Uso",
                                              delta_color="inverse")
                                with col3:
                                    st.metric("Valor Global", f"R$ {empresa[col_global]:,.0f}")
                                with col4:
                                    st.metric("Utilizado", f"R$ {empresa[col_valor_usado]:,.0f}")
                                with col5:
                                    st.metric("Saldo Restante", f"R$ {empresa[col_saldo_restante]:,.0f}")
                                with col6:
                                    st.metric("Saldo vs Utilizado", f"{diferenca:.1f}%", delta=f"+{diferenca:.1f}%",
                                              delta_color="inverse")

                            st.error(f"🚨 **{len(df_avaliar)} contratos com baixo uso - Avaliar necessidade**")
                        else:
                            st.success("🎉 Todos os contratos têm uso acima de 30%!")

                    # ATUALIZAR RESUMO EXECUTIVO
                    st.markdown("---")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("📊 Total Empresas", len(df_empresas))
                    with col2:
                        st.metric("🚨 >70% Uso", len(df_urgente), delta=f"+{len(df_urgente)}")
                    with col3:
                        st.metric("🟢 30%-70% Uso", len(df_renovar), delta=f"+{len(df_renovar)}")
                    with col4:
                        st.metric("🟡 <30% Uso", len(df_avaliar), delta=f"-{len(df_avaliar)}", delta_color="inverse")

                    # LEGENDA EXPLICATIVA
                    with st.expander("📖 Legenda dos Status"):
                        st.markdown("""
                            **🚨 URGENTE - RENOVAR IMEDIATO**
                            - Eficiência (Uso) > 70%
                            - Contrato com alto consumo
                            - Renovar imediatamente para evitar interrupção

                            **🟢 RENOVAR (15 dias) do período de vigência**
                            - Eficiência (Uso) entre 30% e 70%
                            - Contrato com uso moderado
                            - Renovar dentro do prazo estimado

                            **🟡 AVALIAR COM CALMA**
                            - Eficiência (Uso) < 30%
                            - Contrato com baixo consumo
                            - Avaliar se o contrato ainda é necessário
                        """)

                else:
                    st.warning("⚠️ Não há dados válidos para exibir o gráfico após a filtragem.")

            else:
                st.error("❌ Colunas necessárias não encontradas no DataFrame. Verifique os nomes das colunas.")
            # ==============================
            # BOTÕES DE DOWNLOAD
            # ==============================
            st.markdown("---")
            st.subheader("📥 Exportar Dados Completos")

            df_para_download = limpar_dataframe_para_download(df)

            col_dl1, col_dl2, col_dl3 = st.columns(3)

            with col_dl1:
                csv_data = converter_para_csv(df_para_download)
                st.download_button(
                    label="💾 Baixar CSV Completo",
                    data=csv_data,
                    file_name="contratos_completos.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col_dl2:
                excel_data = converter_para_excel(df_para_download)
                st.download_button(
                    label="📊 Baixar Excel Completo",
                    data=excel_data,
                    file_name="contratos_completos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col_dl3:
                json_data = converter_para_json(df_para_download)
                st.download_button(
                        label="🔤 Baixar JSON Completo",
                        data=json_data,
                        file_name="contratos_completos.json",
                        mime="application/json",
                        use_container_width=True
                )

            st.info("💡 Os downloads incluem todos os dados da planilha original, não apenas os filtrados.")

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")

else:
    st.info("📁 Por favor, faça o upload de uma planilha para começar.")