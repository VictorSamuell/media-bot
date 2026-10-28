import DeleteFile from "./DeleteFile";
import { readSession, saveSession, removeSession, SESSION_STORAGE_KEY } from "./session";
import RenameForm from "./RenameForm";
import { useEffect, useRef, useState } from "react";
import { kinds, icons, category, request, type MediaFile } from "./library";
import "./App.css";
const mb = (n: number) =>
  `${n.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} MB`;
const art = (id: string) => (parseInt(id.slice(0, 6), 16) % 8) + 1;
function Cover({ id, name }: { id: string; name: string }) {
  return (
    <div className={`cover art-${art(id)}`} aria-hidden="true">
      <div className="cover-grid" />
      <div className="orb" />
      <div className="orbit" />
      <span className="cover-edition">
        MEDIA SAVER / {category(name).toUpperCase()}
      </span>
      <div className="cover-title">
        <span>{name.replace(/\.[^.]+$/, "")}</span>
      </div>
      <span className="cover-bottom">EXPLORE. APRENDA. GUARDE.</span>
    </div>
  );
}
export default function App() {
  const [files, setFiles] = useState<MediaFile[]>([]);
  const [key, setKey] = useState("");
  const [expiresAt, setExpiresAt] = useState(0);
  const [code, setCode] = useState("");
  const [restoring, setRestoring] = useState(true);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [matched, setMatched] = useState(0);
  const [usage, setUsage] = useState({count:0, bytes:0});
  const requestNumber = useRef(0);
  async function refresh(session = key) {
    const number = ++requestNumber.current;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({page:String(page),page_size:'24',q:query,kind,sort});
      if (onlyFavorites) params.set('favorites_only', 'true');
      const response = await request('/api/files?' + params, session);
      const data = await response.json();
      if (number !== requestNumber.current) return;
      setPage(data.page); setPages(data.pages); setMatched(data.total); setUsage(data.usage);
      setFavorites(data.favorites);
      setDetail(null);
      setFiles(
        data.files.map(
          (f: {
            id: string;
            name: string;
            size: number;
            created_at: string;
          }) => ({
            id: f.id,
            name: f.name,
            size: f.size / 1_000_000,
            date: f.created_at,
            kind: category(f.name),
            note: `Salvo em ${new Date(f.created_at.replace(" ", "T") + "Z").toLocaleString("pt-BR")}`,
          }),
        ),
      );
      setConnected(true);
      setFeature(0);
    } catch (e) {
      if (number !== requestNumber.current) return;
      setError(
        e instanceof Error ? e.message : "Não foi possível conectar à API.",
      );
    } finally {
      if (number === requestNumber.current) {setLoading(false); setRestoring(false);}
    }
  }
  function clearSession() {
    ++requestNumber.current;
    removeSession(); setExpiresAt(0); setRestoring(false);
    setConnected(false); setFiles([]); setKey(''); setCode('');
    setFavorites([]); setDetail(null);
  }
  useEffect(() => {
    const expired = () => {clearSession(); setError('Sessão expirada. Envie /login ao bot para entrar novamente.');};
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, []);
  useEffect(() => {
    const saved = readSession();
    if (saved) {
      setKey(saved.token); setExpiresAt(saved.expiresAt);
      void refresh(saved.token);
    } else {
      setRestoring(false);
    }
    const syncLogout = (event: StorageEvent) => {
      if (event.key === SESSION_STORAGE_KEY && event.newValue === null) clearSession();
    };
    window.addEventListener('storage', syncLogout);
    return () => window.removeEventListener('storage', syncLogout);
  }, []);
  useEffect(() => {
    if (!expiresAt) return;
    const check = () => {
      if (Date.now() >= expiresAt) {
        clearSession(); setError('Suas 2 horas de acesso terminaram. Envie /login ao bot.');
      }
    };
    const timer = window.setTimeout(check, Math.max(0, expiresAt - Date.now()));
    window.addEventListener('focus', check);
    return () => {clearTimeout(timer); window.removeEventListener('focus', check);};
  }, [expiresAt]);
  async function login() {
    setLoading(true); setError('');
    try {
      const response = await request('/api/auth/login', '', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code:code.trim()})
      });
      const session = await response.json();
      const expires = Date.now() + session.expires_in * 1000;
      saveSession({token:session.token, expiresAt:expires});
      setExpiresAt(expires);
      setKey(session.token); setCode('');
      await refresh(session.token);
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível entrar.');}
    finally {setLoading(false);}
  }
  async function logout() {
    setLoading(true); setError('');
    try {
      await request('/api/auth/logout', key, {method:'POST'});
      clearSession();
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível encerrar a sessão. Tente novamente.');}
    finally {setLoading(false);}
  }
  async function download(file: MediaFile) {
    setError("");
    try {
      const response = await request(`/api/files/${file.id}/download`, key);
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no download.");
    }
  }
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("Todos");
  const [sort, setSort] = useState("recent");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [feature, setFeature] = useState(0);
  const visible = files;
  useEffect(() => {
    if (!connected || !key) return;
    // Debounce busca e ignore respostas de uma seleção anterior.
    ++requestNumber.current;
    setLoading(true);
    const timer = setTimeout(() => void refresh(), 250);
    return () => {clearTimeout(timer); ++requestNumber.current;};
  }, [page, query, kind, sort, onlyFavorites]);
  const selected = files.find((f) => f.id === detail);
  const featured = files[feature];
  const featureCount = Math.min(files.length, 4);
  const total = usage.bytes / 1_000_000;
  function reset() {
    setPage(1);
    setQuery("");
    setKind("Todos");
    setOnlyFavorites(false);
    setDetail(null);
  }
  const favoritePending = useRef(false);
  const [savingFavorite, setSavingFavorite] = useState(false);
  async function favorite(id: string) {
    if (favoritePending.current) return;
    favoritePending.current = true;
    setSavingFavorite(true); setError('');
    try {
      await request(`/api/files/${id}/favorite`, key, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({enabled:!favorites.includes(id)})
      });
      await refresh();
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível salvar o favorito.');}
    finally {favoritePending.current = false; setSavingFavorite(false);}
  }
  if (!connected && (restoring || key)) return (
    <main className="login-panel">
      <h1>{restoring || loading ? 'Restaurando seu acesso…' : 'Não foi possível carregar a biblioteca'}</h1>
      <p>Sua sessão salva será verificada pela API. Não é necessário pedir outro código enquanto ela estiver válida.</p>
      {error && <p role="alert">{error}</p>}
      {!loading && !restoring && <>
        <button className="primary" onClick={() => void refresh()}>Tentar novamente</button>
        <button className="primary" onClick={() => {clearSession();setError('');}}>Usar outro código</button>
      </>}
    </main>
  );
  if (!connected)
    return (
      <main className="login-panel">
        <h1>Entre na sua biblioteca</h1>
        <p>Envie /login na conversa privada com o bot e cole o código recebido. Ele vale por 5 minutos e só pode ser usado uma vez.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void login();
          }}
        >
          <label>
            Código do Telegram
            <input
              type="password"
              autoComplete="one-time-code"
              maxLength={16}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          <button className="primary" disabled={loading}>
            {loading ? "Conectando…" : "Abrir biblioteca"}
          </button>
        </form>
        {error && <p role="alert">{error}</p>}
      </main>
    );
  return (
    <div className="steam-shell">
      <header className="app-header">
        <a href="#main" className="brand" onClick={reset}>
          <span className="brand-mark">↘</span>MEDIA<span>SAVER</span>
        </a>
        <nav aria-label="Navegação principal">
          <button className={!onlyFavorites ? "active" : ""} onClick={reset}>
            BIBLIOTECA
          </button>
          <button
            className={onlyFavorites ? "active" : ""}
            onClick={() => {
              reset();
              setOnlyFavorites(true); setPage(1);
            }}
          >
            FAVORITOS
          </button>
          <a href="https://t.me/media_vss_bot" target="_blank" rel="noreferrer">
            TELEGRAM ↗
          </a>
        </nav>
        <div className="user">
          <span className="status-dot" />
          LOCAL<span className="avatar">M</span>
        </div>
      </header>
      <aside className="sidebar">
        <button className="home" onClick={reset}>
          ▦ <span>Página inicial</span>
          <span>⌂</span>
        </button>
        <label className="sidebar-select">
          <span className="sr-only">Filtrar por tipo</span>
          <select value={kind} onChange={(e) => (setPage(1), setKind(e.target.value))}>
            <option value="Todos">Todos os arquivos</option>
            {kinds.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </label>
        <label className="side-search">
          <span>⌕</span>
          <input
            aria-label="Buscar arquivos"
            placeholder="Buscar na biblioteca"
            value={query}
            onChange={(e) => (setPage(1), setQuery(e.target.value))}
          />
          {query && (
            <button onClick={() => {setPage(1);setQuery("");}} aria-label="Limpar busca">
              ×
            </button>
          )}
        </label>
        <button
          className={`section-label ${onlyFavorites ? "selected" : ""}`}
          onClick={() => {
            (setPage(1), setOnlyFavorites(!onlyFavorites));
            setDetail(null);
          }}
        >
          ☆ FAVORITOS <span>({favorites.length})</span>
        </button>
        {favorites.length === 0 ? (
          <p className="favorite-hint">
            Marque uma estrela para guardar seus preferidos.
          </p>
        ) : (
          files
            .filter((f) => favorites.includes(f.id))
            .map((f) => (
              <button
                className="side-file"
                key={f.id}
                onClick={() => setDetail(f.id)}
              >
                <span className={`mini-art art-${art(f.id)}`}>
                  {icons[f.kind]}
                </span>
                {f.name}
              </button>
            ))
        )}
        {favorites.length > 0 && <p className="favorite-hint">A lista acima mostra favoritos desta página. Clique em FAVORITOS para ver todos.</p>}
        <div className="section-label">
          NESTA PÁGINA <span>({visible.length})</span>
        </div>
        <div className="side-files">
          {visible.map((f) => (
            <button
              className={`side-file ${detail === f.id ? "selected" : ""}`}
              key={f.id}
              onClick={() => setDetail(f.id)}
            >
              <span className={`mini-art art-${art(f.id)}`}>
                {icons[f.kind]}
              </span>
              <span>{f.name}</span>
            </button>
          ))}
        </div>
        <div className="side-storage">
          <span>ARMAZENAMENTO</span>
          <strong>{mb(total)}</strong>
          <div className="storage-track">
            <i />
          </div>
          <small>{usage.count} arquivos · biblioteca local</small>
        </div>
      </aside>
      <main id="main">
        <div className="connection-tools">
          <button disabled={loading} onClick={() => void refresh()}>
            {loading ? "Atualizando…" : "Atualizar"}
          </button>
          <button
            disabled={loading}
            onClick={() => void logout()}
          >
            Sair
          </button>
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="breadcrumb">
          Meu espaço <span>/</span> Biblioteca{" "}
          <span className="demo-badge">LOCAL</span>
        </div>
        <div className="title-row">
          <div>
            <h1>
              Sua próxima descoberta
              <br />
              já está na biblioteca.
            </h1>
            <p>Vídeos, ideias e inspirações. Tudo o que vale guardar.</p>
          </div>
          <span className="collection-count">
            {usage.count}{" "}
            <small>
              ARQUIVOS
              <br />
              NA COLEÇÃO
            </small>
          </span>
        </div>
        {selected ? (
          <section className="detail-panel">
            <Cover id={selected.id} name={selected.name} />
            <div>
              <button className="back" onClick={() => setDetail(null)}>
                ← Voltar à biblioteca
              </button>
              <span className="kicker">{selected.kind} / ARQUIVO SALVO</span>
              <h2>{selected.name}</h2>
              <p>{selected.note}</p>
              <div className="metadata">
                <span>{mb(selected.size)}</span>
                <span>{selected.name.split(".").pop()?.toUpperCase()}</span>
              </div>
              <button className="primary" disabled={savingFavorite} onClick={() => void favorite(selected.id)}>
                {favorites.includes(selected.id)
                  ? "★ Remover dos favoritos"
                  : "☆ Adicionar aos favoritos"}
              </button>
              <button className="primary" onClick={() => download(selected)}>
                Baixar arquivo ↓
              </button>
              <RenameForm key={selected.id} file={selected} accessKey={key} onRenamed={(id, name) => {
                setFiles(previous => previous.map(file => file.id === id ? {...file, name, kind: category(name)} : file));
                void refresh();
              }} />
              <DeleteFile key={`delete-${selected.id}`} file={selected} accessKey={key} onDeleted={(id) => {
                setDetail(null);
                setFiles(previous => previous.filter(file => file.id !== id));
                setFavorites(previous => previous.filter(value => value !== id));
                void refresh();
              }} />
              <p className="disclaimer">
                Arquivo disponível na biblioteca do bot.
              </p>
            </div>
          </section>
        ) : featured ? (
          <section className="featured" aria-label="Destaques da biblioteca">
            <div className="feature-visual">
              <Cover id={featured.id} name={featured.name} />
              <span className="feature-stamp">EM DESTAQUE</span>
            </div>
            <div className="feature-info">
              <span className="kicker">DA SUA COLEÇÃO</span>
              <h2>{featured.name.replace(/\.[^.]+$/, "")}</h2>
              <p>
                {featured.note}. Um espaço para revisitar o que inspira você.
              </p>
              <div className="metadata">
                <span>{featured.kind}</span>
                <span>{mb(featured.size)}</span>
              </div>
              <button
                className="primary"
                onClick={() => setDetail(featured.id)}
              >
                Explorar arquivo <span>→</span>
              </button>
              <div className="carousel">
                <div className="dots">
                  {files.slice(0, 4).map((f, i) => (
                    <button
                      key={f.id}
                      className={feature === i ? "active" : ""}
                      aria-label={`Destacar ${f.name}`}
                      aria-pressed={feature === i}
                      onClick={() => setFeature(i)}
                    />
                  ))}
                </div>
                <button
                  aria-label="Destaque anterior"
                  onClick={() =>
                    setFeature((feature + featureCount - 1) % featureCount)
                  }
                >
                  ‹
                </button>
                <button
                  aria-label="Próximo destaque"
                  onClick={() => setFeature((feature + 1) % featureCount)}
                >
                  ›
                </button>
              </div>
            </div>
          </section>
        ) : null}
        <section className="shelf" aria-label="Arquivos da biblioteca">
          <div className="shelf-heading">
            <h2>
              {onlyFavorites
                ? "Seus favoritos"
                : query
                  ? "Resultados da busca"
                  : kind === "Todos"
                    ? "Adicionados recentemente"
                    : kind}
              <span>{matched}</span>
            </h2>
            <div className="shelf-line" />
            <label>
              <span className="sr-only">Ordenar arquivos</span>
              <select value={sort} onChange={(e) => (setPage(1), setSort(e.target.value))}>
                <option value="recent">Mais recentes</option>
                <option value="name">Nome A–Z</option>
                <option value="size">Maior tamanho</option>
              </select>
            </label>
            <div className="view-toggle">
              <button
                aria-label="Visualização em capas"
                aria-pressed={view === "grid"}
                className={view === "grid" ? "active" : ""}
                onClick={() => setView("grid")}
              >
                ▦
              </button>
              <button
                aria-label="Visualização em lista"
                aria-pressed={view === "list"}
                className={view === "list" ? "active" : ""}
                onClick={() => setView("list")}
              >
                ☰
              </button>
            </div>
          </div>
          <div className="filter-row" role="group" aria-label="Categorias">
            {["Todos", ...kinds].map((k) => (
              <button
                key={k}
                aria-pressed={kind === k}
                className={kind === k ? "active" : ""}
                onClick={() => (setPage(1), setKind(k))}
              >
                {k}
              </button>
            ))}
            <button
              className={onlyFavorites ? "active" : ""}
              aria-pressed={onlyFavorites}
              onClick={() => (setPage(1), setOnlyFavorites(!onlyFavorites))}
            >
              ☆ Favoritos
            </button>
          </div>
          <div className={`file-collection ${view}`}>
            {visible.map((f) => (
              <article className="file-card" key={f.id}>
                <button
                  className="cover-button"
                  onClick={() => setDetail(f.id)}
                  aria-label={`Ver detalhes de ${f.name}`}
                >
                  <Cover id={f.id} name={f.name} />
                  <span className="cover-hover">EXPLORAR ↗</span>
                </button>
                <div className="card-info">
                  <button
                    className="file-title"
                    onClick={() => setDetail(f.id)}
                  >
                    {f.name}
                  </button>
                  <span>
                    {f.kind} <i>·</i> {mb(f.size)}
                  </span>
                </div>
                <button
                  className={`favorite ${favorites.includes(f.id) ? "saved" : ""}`}
                  aria-label={`Favoritar ${f.name}`}
                  aria-pressed={favorites.includes(f.id)}
                  disabled={savingFavorite}
                  onClick={() => void favorite(f.id)}
                >
                  {favorites.includes(f.id) ? "★" : "☆"}
                </button>
              </article>
            ))}
          </div>
          {!visible.length && (
            <div className="empty" role="status">
              <span>⌕</span>
              <h3>
                {onlyFavorites && !favorites.length
                  ? "Sua prateleira de favoritos está vazia"
                  : !usage.count
                    ? "Sua biblioteca está vazia"
                    : "Nenhum arquivo encontrado"}
              </h3>
              <p>
                {onlyFavorites && !favorites.length
                  ? "Use a estrela nas capas para reunir seus preferidos."
                  : !usage.count
                    ? "Salve um arquivo pelo Telegram e clique em Atualizar."
                    : "Tente outro nome ou remova os filtros."}
              </p>
              <button className="primary" onClick={reset}>
                Mostrar todos os arquivos
              </button>
            </div>
          )}
          <nav className="pagination" aria-label="Páginas da biblioteca">
            <button className="primary" disabled={loading || page <= 1} onClick={()=>setPage(page-1)}>← Anterior</button>
            <span role="status">{loading ? 'Carregando…' : `Página ${page} de ${pages}`}</span>
            <button className="primary" disabled={loading || page >= pages} onClick={()=>setPage(page+1)}>Próxima →</button>
          </nav>
          <div className="collection-footer">
            <span aria-live="polite">
              {visible.length} de {matched} resultados · {usage.count} arquivos na biblioteca
            </span>
            <span>Seu conteúdo. Do seu jeito.</span>
          </div>
        </section>
        <div className="demo-note">
          <span>ⓘ</span>
          <p>
            <strong>Sua biblioteca local.</strong> Arquivos salvos pelo bot. As
            capas são geradas a partir dos nomes. Favoritos ficam salvos na sua biblioteca, mesmo após sair.
          </p>
        </div>
      </main>
      <footer className="statusbar">
        <span>
          <i className="status-dot" /> MEDIA SAVER <b> / </b> Biblioteca local
        </span>
        <span>BIBLIOTECA CONECTADA À API LOCAL</span>
      </footer>
    </div>
  );
}
