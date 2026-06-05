// Cloudflare Pages 边缘鉴权：对全站启用 HTTP Basic Auth
// 密码来自 Pages 环境变量 SITE_PASSWORD（不写进公开仓库）
// 目的：功能地图含客户系统接口/字段，不公开裸奔
export async function onRequest(context) {
  const { request, env, next } = context;
  const USER = 'mike';
  const PASS = env.SITE_PASSWORD || '';
  const expected = 'Basic ' + btoa(USER + ':' + PASS);
  const got = request.headers.get('Authorization') || '';
  if (!PASS || got !== expected) {
    return new Response('需要授权访问', {
      status: 401,
      headers: {
        'WWW-Authenticate': 'Basic realm="karaithy-dev", charset="UTF-8"',
        'Content-Type': 'text/plain; charset=utf-8',
      },
    });
  }
  return next();
}
