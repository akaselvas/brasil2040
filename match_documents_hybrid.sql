create or replace function public.match_documents_hybrid(
  query_embedding vector,
  query_text text,
  match_count integer default 10,
  rrf_k integer default 60,
  candidates integer default 50
)
returns table(id bigint, file text, page integer, text text, similarity double precision)
language sql
stable
as $$
with q as (
select replace(plainto_tsquery('portuguese', query_text)::text, '&', '|')::tsquery as tsq
),
  semantic as (
select id, row_number() over (order by dist) as rank
from (
select d.id, d.embedding <=> query_embedding as dist
from documents d
order by dist
limit candidates
) s
),
  lexical as (
select id, row_number() over (order by r desc) as rank
from (
select d.id, ts_rank_cd(d.fts, q.tsq) as r
from documents d, q
where d.fts @@ q.tsq
order by r desc
limit candidates
) l
),
  fused as (
select coalesce(s.id, l.id) as id,
           coalesce(1.0 / (rrf_k + s.rank), 0) + 0.5 * coalesce(1.0 / (rrf_k + l.rank), 0) as score
from semantic s
full outer join lexical l on s.id = l.id
)
select d.id, d.file, d.page, d.text, f.score::double precision as similarity
from fused f
join documents d on d.id = f.id
order by f.score desc
limit match_count;
$$;