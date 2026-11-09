"""Perguntas de visitantes com o(s) trecho(s) da base de conhecimento que deveriam ser recuperados.

``expect`` é uma lista de (arquivo, trecho do título); basta recuperar UM deles. ``messages`` traz o histórico de
mensagens do usuário (para testar perguntas de acompanhamento, onde a última mensagem sozinha não basta).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    messages: tuple[str, ...]
    expect: tuple[tuple[str, str], ...]
    group: str  # factual | projetos | portfolio | acompanhamento | en


CASES: list[Case] = [
    # --- sobre o Heriberto (PT) ---
    Case("trabalho", ("Onde o Heriberto trabalha hoje?",), (("perfil.md", "Experiência atual"),), "factual"),
    Case("dss_tech", ("Quais tecnologias ele usou no projeto DSS?",), (("perfil.md", "Projeto DSS"),), "factual"),
    Case("visao", ("Ele tem experiência com visão computacional?",), (("perfil.md", "Outros projetos"),), "factual"),
    Case("churn", ("Como foi o trabalho de churn e forecast na Oi?",), (("perfil.md", "Outros projetos"),), "factual"),
    Case("formacao", ("Qual a formação dele?",), (("perfil.md", "Formação"),), "factual"),
    Case("tcc", ("Qual foi o tema do TCC?",), (("perfil.md", "Formação"),), "factual"),
    Case("bancos", ("Ele sabe MongoDB e Redis?",), (("perfil.md", "Habilidades"), ("perfil.md", "Projeto DSS")), "factual"),
    Case("aula", ("Ele já foi professor?",), (("perfil.md", "Docência"),), "factual"),
    Case("hobbies", ("Quais são os hobbies dele?",), (("perfil.md", "Hobbies"),), "factual"),
    Case("contato", ("Como posso entrar em contato com ele?",), (("perfil.md", "Contato"),), "factual"),
    Case("objetivo", ("Qual o objetivo de carreira dele?",), (("perfil.md", "Contato"),), "factual"),
    Case("idioma", ("Qual o nível de inglês dele?",), (("perfil.md", "Perfil"),), "factual"),
    # --- sobre o portfólio ---
    Case("chat_como", ("Como esse chat funciona por dentro?",), (("portfolio.md", "Como o chat funciona"),), "portfolio"),
    Case("hospedagem", ("Onde o portfólio vai ser hospedado?",), (("portfolio.md", "Como o portfólio é organizado"),), "portfolio"),
    Case("estado", ("Algum projeto já está no ar?",), (("portfolio.md", "Estado dos projetos"), ("projetos.md", "Portfólio")), "portfolio"),
    Case("modelo", ("Qual modelo de IA o chat usa?",), (("portfolio.md", "Como o chat funciona"),), "portfolio"),
    Case("sql_seguro", ("Como o SQL do agente de planilhas é protegido?",), (("portfolio.md", "Decisões de engenharia"), ("projetos.md", "02")), "portfolio"),
    # --- catálogo de projetos ---
    Case("filmes", ("Como funciona o recomendador de filmes?",), (("projetos.md", "01"), ("portfolio.md", "Decisões de engenharia")), "projetos"),
    Case("ocr", ("Qual projeto vai converter documentos escaneados em texto?",), (("projetos.md", "03"),), "projetos"),
    Case("pptx", ("Vai ter um gerador de apresentações?",), (("projetos.md", "04"),), "projetos"),
    Case("rpg", ("Tem algum projeto de narrador de RPG?",), (("projetos.md", "05"),), "projetos"),
    Case("ibge", ("Que projeto usa dados do IBGE e do SUS?",), (("projetos.md", "06"),), "projetos"),
    Case("fases", ("Qual a ordem de implementação dos projetos?",), (("projetos.md", "Ordem sugerida"),), "projetos"),
    Case("custo", ("Que riscos de custo as demos têm?",), (("projetos.md", "Arquitetura comum"),), "projetos"),
    Case("afiliados", ("O que é o radar de afiliados?",), (("projetos.md", "09"),), "projetos"),
    # --- acompanhamento: a última mensagem sozinha é ambígua ---
    Case("seg_dss", ("Fale do projeto DSS", "e quais tecnologias ele usou?"), (("perfil.md", "Projeto DSS"),), "acompanhamento"),
    Case("seg_visao", ("Ele sabe visão computacional?", "e em qual cliente foi?"), (("perfil.md", "Outros projetos"),), "acompanhamento"),
    Case("seg_filmes", ("Fale do recomendador de filmes", "como ele mede a qualidade?"), (("projetos.md", "01"), ("portfolio.md", "Decisões de engenharia")), "acompanhamento"),
    # --- variações da mesma palavra (trabalha/trabalhou/trabalho, atua/atuou...): a base não usa a forma da pergunta ---
    Case("mo_trabalha", ("Onde ele trabalha?",), (("perfil.md", "Experiência atual"),), "morfologia"),
    Case("mo_trabalhou_agentes", ("Ele já trabalhou com agentes de IA?",), (("perfil.md", "Projeto DSS"),), "morfologia"),
    Case("mo_atua", ("Em qual empresa ele atua?",), (("perfil.md", "Experiência atual"),), "morfologia"),
    Case("mo_anos", ("Quantos anos de experiência ele tem?",), (("perfil.md", "Perfil"),), "morfologia"),
    Case("mo_desenvolveu", ("O que ele desenvolveu para clientes?",), (("perfil.md", "Outros projetos"), ("perfil.md", "Projeto DSS")), "morfologia"),
    Case("mo_aprende", ("Ele estudou onde?",), (("perfil.md", "Formação"),), "morfologia"),
    # --- English ---
    Case("en_work", ("Where does he work now?",), (("profile.en.md", "Current job"),), "en"),
    Case("en_dss", ("What technologies did he use in the DSS project?",), (("profile.en.md", "DSS project"),), "en"),
    Case("en_edu", ("What is his education?",), (("profile.en.md", "Education"),), "en"),
    Case("en_cv", ("Does he have computer vision experience?",), (("profile.en.md", "Other data science"),), "en"),
    Case("en_hobbies", ("What are his hobbies?",), (("profile.en.md", "Hobbies"),), "en"),
    Case("en_contact", ("How can I contact him?",), (("profile.en.md", "Profile"),), "en"),
    Case("en_teach", ("Has he ever taught?",), (("profile.en.md", "Teaching"),), "en"),
]
