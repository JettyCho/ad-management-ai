-- DuckDB 초기 설정: MCP 서버 시작 시 자동 실행
-- INSTALL은 이미 설치된 경우 스킵되므로 매번 실행해도 안전

-- MySQL 연결 (Teleport 포트포워딩 후 ATTACH)
INSTALL mysql;
LOAD mysql;

-- S3 파일 쿼리 (Parquet, CSV, JSON)
INSTALL httpfs;
LOAD httpfs;
INSTALL aws;
LOAD aws;

-- 데이터 포맷 (JSON, Parquet, Excel)
INSTALL json;
LOAD json;
INSTALL parquet;
LOAD parquet;
INSTALL excel;
LOAD excel;

-- 풀텍스트 검색
INSTALL fts;
LOAD fts;

-- 벡터 유사도 검색 (RAG)
INSTALL vss;
LOAD vss;
