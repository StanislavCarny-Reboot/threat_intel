"""Threat Intel Dashboard - Streamlit app."""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../backend/.env"))

QUERY_SOURCES = """
    SELECT s.source_name, count(*) AS article_count
    FROM extracted_article_urls_stano u
    LEFT JOIN sources_master_list s ON u.source_uuid = s.source_uuid
    GROUP BY s.source_uuid, s.source_name
    ORDER BY count(*) DESC
"""


def get_engine():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(
        sync_url,
        connect_args={"sslmode": "prefer", "gssencmode": "disable"},
    )


@st.cache_data(ttl=300)
def fetch_sources() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(QUERY_SOURCES), conn)


def main() -> None:
    st.set_page_config(page_title="Threat Intel Dashboard", layout="wide")
    st.title("Threat Intel Dashboard")
    st.subheader("Articles per Source")

    with st.spinner("Loading data..."):
        try:
            df = fetch_sources()
        except Exception as exc:
            st.error(f"Failed to load data: {exc}")
            return

    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("Filter source", placeholder="Type to filter...")
    with col2:
        st.write("")
        st.write("")
        if st.button("Refresh"):
            fetch_sources.clear()
            st.rerun()

    filtered = (
        df[df["source_name"].str.contains(search, case=False, na=False)]
        if search
        else df
    )

    st.dataframe(
        filtered,
        column_config={
            "source_name": st.column_config.TextColumn("Source", width="large"),
            "article_count": st.column_config.NumberColumn("Articles", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"Showing {len(filtered)} of {len(df)} sources | Articles: {filtered['article_count'].sum():,}"
    )


if __name__ == "__main__":
    main()
