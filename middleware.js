export const config = {
  matcher: '/admin.html',
};

export default function middleware(request) {
  const basicAuth = request.headers.get('authorization');

  if (basicAuth) {
    const authValue = basicAuth.split(' ')[1];
    
    // atob is available in Vercel Edge Runtime
    const decoded = atob(authValue);
    const [user, pwd] = decoded.split(':');

    // デフォルトのログイン情報
    // ID: admin
    // パスワード: hubcargo2026
    if (user === 'admin' && pwd === 'hubcargo2026') {
      // 成功時は何も返さない（そのままページを表示する）
      return;
    }
  }

  // 認証失敗時、または初回アクセス時は 401 Unauthorized を返す
  return new Response('認証が必要です。正しいIDとパスワードを入力してください。', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Secure Admin Dashboard"',
      'Content-Type': 'text/plain; charset=utf-8'
    },
  });
}
