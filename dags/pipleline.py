from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    'owner': 'noura',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'execution_timeout': timedelta(hours=4),
}

dag = DAG(
    'banking_reviews_complete_pipeline_dbt',
    default_args=default_args,
    description='Complete Banking Reviews Data Warehouse Pipeline with DBT',
    schedule_interval='@daily',
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['banking', 'reviews', 'dbt', 'data-warehouse'],
)



DBT_PROJECT_PATH = "/home/noura/dbt_project/morocco_banks_reviews"
VENV_PATH = "/home/noura/venv"
SCRIPTS_PATH = "/home/noura/airflow/scripts"




run_scraping_script = BashOperator(
    task_id='run_scraping_script',
    bash_command=f'{VENV_PATH}/bin/python {SCRIPTS_PATH}/script1.py',
    dag=dag,
)

insert_data_to_postgres = BashOperator(
    task_id='insert_data_to_postgres',
    bash_command=f'{VENV_PATH}/bin/python {SCRIPTS_PATH}/insert_into_postgres.py',
    dag=dag,
)




dbt_debug = BashOperator(
    task_id='dbt_debug_check',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt debug
    ''',
    dag=dag,
)


dbt_deps = BashOperator(
    task_id='dbt_install_dependencies',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt deps
    ''',
    dag=dag,
)




dbt_staging = BashOperator(
    task_id='dbt_run_staging',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt run --select models/staging --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)


dbt_intermediate = BashOperator(
    task_id='dbt_run_intermediate',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt run --select models/intermediate --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)


run_lda_analysis = BashOperator(
    task_id='run_lda_topic_analysis',
    bash_command=f'{VENV_PATH}/bin/python {SCRIPTS_PATH}/lda_topic_modeling.py',
    dag=dag,
)


dbt_mart_enriched = BashOperator(
    task_id='dbt_run_mart_enriched',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt run --select models/marts/mart_reviews_enriched.sql --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)


dbt_dimensions = BashOperator(
    task_id='dbt_run_dimensions',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt run --select models/marts/dim_* --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)


dbt_fact_table = BashOperator(
    task_id='dbt_run_fact_table',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt run --select models/marts/fact_reviews.sql --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)




dbt_tests = BashOperator(
    task_id='dbt_run_tests',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt test --vars '{{"execution_date": "{{{{ ds }}}}"}}' --target dev
    ''',
    dag=dag,
)


dbt_docs = BashOperator(
    task_id='dbt_generate_docs',
    bash_command=f'''
    cd {DBT_PROJECT_PATH} && 
    {VENV_PATH}/bin/dbt docs generate --target dev &&
    echo "📚 Documentation DBT générée dans {DBT_PROJECT_PATH}/target/"
    ''',
    dag=dag,
)




create_dashboard_views = PostgresOperator(
    task_id='create_dashboard_materialized_views',
    postgres_conn_id='postgres_default',  
    sql=f'''
    -- Vue pour tendances sentiment par banque
    DROP MATERIALIZED VIEW IF EXISTS marts.mv_sentiment_trends_by_bank CASCADE;
    CREATE MATERIALIZED VIEW marts.mv_sentiment_trends_by_bank AS
    SELECT 
        db.bank_name,
        ds.sentiment,
        DATE_TRUNC('month', TO_DATE(fr.date_avis, 'DD/MM/YYYY')) as month_year,
        COUNT(*) as review_count,
        AVG(fr.rating) as avg_rating,
        ROUND(
            COUNT(CASE WHEN ds.sentiment = 'Positif' THEN 1 END)::DECIMAL / 
            NULLIF(COUNT(*), 0) * 100, 2
        ) as positive_percentage
    FROM marts.fact_reviews fr
    JOIN marts.dim_bank db ON fr.bank_key = db.bank_key
    JOIN marts.dim_sentiment ds ON fr.sentiment_key = ds.sentiment_key
    WHERE fr.review_date IS NOT NULL
    GROUP BY db.bank_name, ds.sentiment, DATE_TRUNC('month', TO_DATE(fr.date_avis, 'DD/MM/YYYY'));
    
    -- Vue pour performance des agences par ville
    DROP MATERIALIZED VIEW IF EXISTS marts.mv_city_bank_performance CASCADE;
    CREATE MATERIALIZED VIEW marts.mv_city_bank_performance AS
    SELECT 
        dl.city,
        db.bank_name,
        COUNT(*) as total_reviews,
        AVG(fr.rating) as avg_rating,
        COUNT(CASE WHEN ds.sentiment = 'Positif' THEN 1 END) as positive_reviews,
        COUNT(CASE WHEN ds.sentiment = 'Negatif' THEN 1 END) as negative_reviews,
        ROUND(
            COUNT(CASE WHEN ds.sentiment = 'Positif' THEN 1 END)::DECIMAL / 
            NULLIF(COUNT(*), 0) * 100, 2
        ) as satisfaction_rate
    FROM marts.fact_reviews fr
    JOIN marts.dim_bank db ON fr.bank_key = db.bank_key
    JOIN marts.dim_location dl ON fr.location_key = dl.location_key
    JOIN marts.dim_sentiment ds ON fr.sentiment_key = ds.sentiment_key
    GROUP BY dl.city, db.bank_name;
    
    -- Vue pour analyse des topics
    DROP MATERIALIZED VIEW IF EXISTS marts.mv_topic_insights CASCADE;
    CREATE MATERIALIZED VIEW marts.mv_topic_insights AS
    SELECT 
        dt.topic_name,
        dt.category,
        COUNT(*) as mentions_count,
        AVG(fr.rating) as avg_rating_for_topic,
        COUNT(CASE WHEN ds.sentiment = 'Positif' THEN 1 END) as positive_mentions,
        COUNT(CASE WHEN ds.sentiment = 'Negatif' THEN 1 END) as negative_mentions,
        STRING_AGG(DISTINCT db.bank_name, ', ' ORDER BY db.bank_name) as banks_mentioned
    FROM marts.fact_reviews fr
    JOIN marts.dim_topic dt ON fr.topic_key = dt.topic_key
    JOIN marts.dim_sentiment ds ON fr.sentiment_key = ds.sentiment_key
    JOIN marts.dim_bank db ON fr.bank_key = db.bank_key
    GROUP BY dt.topic_name, dt.category;
    
    -- Actualiser les statistiques
    ANALYZE marts.mv_sentiment_trends_by_bank;
    ANALYZE marts.mv_city_bank_performance;
    ANALYZE marts.mv_topic_insights;
    
    -- Log de succès
    INSERT INTO public.pipeline_logs (execution_date, step_name, status, message)
    VALUES (CURRENT_DATE, 'create_dashboard_views', 'SUCCESS', 'Vues matérialisées créées pour Looker Studio');
    ''',
    dag=dag,
)



def validate_pipeline_data(**context):
    """Validation des données du pipeline"""
    import psycopg2
    import pandas as pd
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="bank_maroc",
            user="airflow1",
            password="airflow"
        )
        
        
        checks = {
            'total_reviews': "SELECT COUNT(*) as count FROM marts.fact_reviews",
            'banks_count': "SELECT COUNT(DISTINCT bank_key) as count FROM marts.fact_reviews WHERE bank_key > 0",
            'recent_data': "SELECT COUNT(*) as count FROM marts.mart_reviews_enriched WHERE date_avis != 'Date inconnue'",
            'sentiment_distribution': """
                SELECT sentiment, COUNT(*) as count 
                FROM marts.fact_reviews fr 
                JOIN marts.dim_sentiment ds ON fr.sentiment_key = ds.sentiment_key 
                GROUP BY sentiment
            """
        }
        
        results = {}
        for check_name, query in checks.items():
            df = pd.read_sql(query, conn)
            results[check_name] = df.to_dict('records')
            print(f"✅ {check_name}: {df.to_dict('records')}")
        
        conn.close()
        
       
        total_reviews = results['total_reviews'][0]['count']
        banks_count = results['banks_count'][0]['count']
        recent_data = results['recent_data'][0]['count']
        
        if total_reviews < 50:
            raise ValueError(f"❌ Nombre total d'avis insuffisant: {total_reviews}")
        
        if banks_count < 3:
            raise ValueError(f"❌ Nombre de banques insuffisant: {banks_count}")
        
        if recent_data < 10:
            print(f"⚠️  Warning: Peu de données avec dates valides: {recent_data}")
        
        print(f"🎉 VALIDATION RÉUSSIE!")
        print(f"📊 Total avis: {total_reviews}")
        print(f"🏦 Banques: {banks_count}")
        print(f"📅 Données datées: {recent_data}")
        
        return results
        
    except Exception as e:
        print(f"❌ ERREUR lors de la validation: {e}")
        raise


validate_data_quality = PythonOperator(
    task_id='validate_pipeline_data_quality',
    python_callable=validate_pipeline_data,
    dag=dag,
)


send_success_notification = BashOperator(
    task_id='send_pipeline_success_notification',
    bash_command=f'''
    echo "🎉 PIPELINE DATA WAREHOUSE TERMINÉ AVEC SUCCÈS!"
    echo "================================================"
    ''',
    dag=dag,
)




run_scraping_script >> insert_data_to_postgres


insert_data_to_postgres >> dbt_debug >> dbt_deps


dbt_deps >> dbt_staging >> dbt_intermediate


dbt_intermediate >> run_lda_analysis


run_lda_analysis >> dbt_mart_enriched >> dbt_dimensions >> dbt_fact_table


dbt_fact_table >> dbt_tests >> dbt_docs


dbt_docs >> create_dashboard_views


create_dashboard_views >> validate_data_quality >> send_success_notification
