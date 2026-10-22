"""Existing catalog, comparison, search and selected chat, inside the map overlay."""
import os
import streamlit as st
from .catalog import TYPE_KO
from .ui_rag import render_chat,render_global_chat,render_natural_search,index_counts
from .generation_compare import render_generation_analysis

def format_abilities(abilities, generation, ability_ko):
    """특성 이름을 한국어로 변환."""
    if generation < 3:
        return "도입 이전"

    if not abilities:
        return "미확인"

    result = []

    for ability in abilities:
        en_name = ability.get("name", "")
        ko_name = ability_ko.get(en_name, en_name)

        result.append(ko_name)

    return ", ".join(result) or "미확인"


def show_pokemon_image(pokemon_id, image_dir, varieties):
    """포켓몬 이미지 표시 및 이로치 전환."""
    show_shiny = st.checkbox(
        "이로치 이미지 보기",
        key=f"shiny_{pokemon_id}"
    )

    image_type = "shiny" if show_shiny else "official"

    image_path = (
        image_dir / image_type / f"{pokemon_id}.png"
    )

    if image_path.is_file():
        st.image(str(image_path), width=260)
        return

    # 이로치 이미지가 없다면 일반 이미지 사용
    if show_shiny:
        normal_path = (
            image_dir / "official" / f"{pokemon_id}.png"
        )

        if normal_path.is_file():
            st.image(str(normal_path), width=260)
            st.caption("이로치 이미지가 없어 일반 이미지를 표시합니다.")
            return

    # 로컬 파일이 없으면 기존 이미지 URL 사용
    variety = varieties.get(pokemon_id, {})
    image_url = variety.get("image_url")

    if image_url:
        st.image(image_url, width=260)
    else:
        st.info("등록된 이미지가 없습니다.")


def render_lab(config,db,image_dir):
    ability_ko=db.ability_names
    pending = st.session_state.pop('pending_pokemon', None)
    if pending:
        st.session_state['name_query'] = ''
        st.session_state['selected_pokemon'] = pending['pokemon_id']
        st.session_state['selected_generation'] = pending['generation']
        st.session_state['show_chat_hint'] = True
        st.session_state['preferred_tab'] = pending.get('tab','질문하기')
        st.session_state['chat_mode'] = '선택한 포켓몬 질문'

    with st.container(border=True):
        st.header("포켓몬 찾기")

        query = st.text_input(
            "이름 검색",
            placeholder="피카츄 또는 pikachu", key='name_query'
        )

        ids = [
            i for i in db.varieties
            if query.lower() in db.label(i).lower()
        ]

        if not ids:
            st.info("일치하는 포켓몬이 없습니다.")

        pokemon_id = st.selectbox(
            "포켓몬과 형태",
            ids,
            format_func=db.label, key='selected_pokemon'
        )

        rows = db.records_for(pokemon_id)

        if not rows:
            st.info("이 형태의 세대 정보가 확인되지 않았습니다.")

        available_generations = [r['generation'] for r in rows]
        if st.session_state.get('selected_generation') not in available_generations:
            st.session_state['selected_generation'] = available_generations[-1] if available_generations else None
        generation = st.selectbox(
            "세대",
            available_generations,
            format_func=lambda x: f"{x}세대", key='selected_generation'
        )

        st.divider()
        st.metric("수집된 포켓몬 종", len(db.species))
        counts = index_counts(config)
        st.caption(f"RAG 색인 · 메타데이터 {counts.get('pokemon_meta', 0):,} · 문서 청크 {counts.get('pokemon_docs', 0):,}")

        if not (os.getenv("GMS_KEY") or os.getenv("OPENAI_API_KEY")):
            st.caption("AI 답변 연결에는 API 키 설정이 필요합니다.")


    row = db.index.get((pokemon_id, generation))

    overview, compare, search, chat = st.tabs([
        "도감",
        "세대 비교",
        "조건 검색",
        "질문하기"
    ], default=st.session_state.get('preferred_tab','질문하기'))


    # ----------------------------------
    # 1. 포켓몬 도감
    # ----------------------------------
    with overview:
        if not row: st.info('사이드바에서 포켓몬을 선택해 주세요.')
        else:
            st.subheader(db.label(pokemon_id))

            image_col, info_col = st.columns([1, 2])

            with image_col:
                show_pokemon_image(
                    pokemon_id,
                    image_dir,
                    db.varieties
                )

            with info_col:
                a, b, c = st.columns(3)

                a.metric(
                    "선택한 세대",
                    f"{generation}세대"
                )

                b.metric(
                    "타입",
                    " / ".join(
                        TYPE_KO.get(t, t)
                        for t in row["types"] or []
                    ) or "미확인"
                )

                st.markdown("#### 특성")

                abilities_text = format_abilities(
                    row.get("abilities"),
                    generation,
                    ability_ko
                )

                st.write(abilities_text)

            st.info(
                "이 정보는 세대별 규칙에 대한 기록입니다. "
                "해당 세대의 모든 게임에 등장한다는 뜻은 아닙니다."
            )

            st.markdown("#### 종족값")

            labels = {
                "hp": "HP",
                "attack": "공격",
                "defense": "방어",
                "special": "특수",
                "special_attack": "특수공격",
                "special_defense": "특수방어",
                "speed": "스피드"
            }

            st.dataframe(
                [
                    {
                        "능력치": labels.get(k, k),
                        "값": v
                    }
                    for k, v in row["stats"].items()
                    if v is not None
                ],
                hide_index=True,
                width="stretch"
            )

            st.link_button(
                "PokéAPI 원본 보기",
                row["source_url"]
            )


    # ----------------------------------
    # 2. 세대별 비교
    # ----------------------------------
    with compare:
        if not row: st.info('사이드바에서 포켓몬을 선택해 주세요.')
        else:
            st.subheader("같은 포켓몬의 세대별 변화")

            table = []

            for r in rows:
                table.append({
                    "세대": r["generation"],
                    "타입": ", ".join(
                        TYPE_KO.get(t, t)
                        for t in r["types"] or []
                    ),
                    "특성": format_abilities(
                        r.get("abilities"),
                        r["generation"],
                        ability_ko
                    ),
                    **r["stats"]
                })

            st.dataframe(
                table,
                hide_index=True,
                width="stretch"
            )

            st.caption(
                "1세대의 특수는 이후 세대의 "
                "특수공격·특수방어와 별개로 표시합니다."
            )

            st.link_button(
                "비교 데이터 출처",
                row["source_url"]
            )
            render_generation_analysis(config, db, pokemon_id)


    # ----------------------------------
    # 3. 조건 검색
    # ----------------------------------
    with search:
        st.subheader("조건으로 찾아보기")

        st.caption("선택형 조건 검색과 AI 자연어 탐색을 함께 사용할 수 있습니다.")

        target_gen = st.selectbox(
            "검색 세대",
            db.generations,
            index=len(db.generations) - 1
        )

        target_type = st.selectbox(
            "타입",
            ["전체"] + list(TYPE_KO),
            format_func=lambda x: TYPE_KO.get(x, x)
        )

        total = st.number_input(
            "종족값 합계 최솟값",
            min_value=0,
            max_value=2000,
            value=0,
            step=10
        )

        matches = db.search(
            target_gen,
            None if target_type == "전체" else target_type,
            total
        )

        st.caption(
            f"{len(matches):,}개 형태 · "
            "게임별 등장 여부는 확인되지 않았습니다."
        )

        st.dataframe(
            matches,
            hide_index=True,
            width="stretch"
        )
        st.divider()
        render_natural_search(config, db, target_gen, image_dir)


    # ----------------------------------
    # 4. 질문하기
    # ----------------------------------
    with chat:
        mode=st.radio('질문 모드',['전체 포켓몬 질문','선택한 포켓몬 질문'],horizontal=True,key='chat_mode')
        if mode=='전체 포켓몬 질문': render_global_chat(config, db)
        elif row: render_chat(config, db, pokemon_id, generation)
        else: st.info('사이드바에서 포켓몬과 세대를 선택해 주세요.')
