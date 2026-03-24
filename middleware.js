export const config = {
  // admin.html と API エンドポイント両方を保護
  matcher: ['/admin.html', '/api/:path*'],
};

export default function middleware(request) {
  // 環境変数からID/パスワードを取得 (Vercelダッシュボードで設定)
  const ADMIN_USER = process.env.ADMIN_USER;
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

  // 環境変数が未設定の場合はアクセスを全拒否（フェイルセーフ）
  if (!ADMIN_USER || !ADMIN_PASSWORD) {
    return new Response('サーバー設定エラー: 環境変数が未設定です。', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }

  const basicAuth = request.headers.get('authorization');

  if (basicAuth) {
    const authValue = basicAuth.split(' ')[1];
    const decoded = atob(authValue);
    const [user, ...rest] = decoded.split(':');
    const pwd = rest.join(':'); // パスワード中のコロンを正しく扱う

    if (user === ADMIN_USER && pwd === ADMIN_PASSWORD) {
      // 認証成功時、本来のページへルーティングを継続させる (Vercelの仕様)
      return new Response(null, { headers: { 'x-middleware-next': '1' } });
    }
  }

  // 認証失敗時 or 未認証アクセス → 401
  return new Response('認証が必要です。正しいIDとパスワードを入力してください。', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="HubCargo Admin"',
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
}
