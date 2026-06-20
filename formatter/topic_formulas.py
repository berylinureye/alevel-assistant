"""
A-Level Mathematics (CIE 9709) 官方公式库。

用途：
    生成「优先复习主题」时按 subtopic（或 topic）匹配官方公式，
    替代直接从学生题面抽取的 relevant_formulas（往往带具体数字、噪声）。

查询入口：
    lookup_formulas(subtopic: str, topic: str = "", chapter: str = "") -> list[str]

维护规则：
    - key 使用 normalize() 规则化后的字符串（小写 + 去标点 + 归一 and/& + 去尾复数 s）
    - value 为 LaTeX 字符串列表（外层统一 $...$，方便前端 KaTeX 直接渲染）
    - 每个 subtopic 最多 3 条最核心公式；避免堆砌
    - 如某 subtopic 未显式列出，会按 topic 名称回退
"""
from __future__ import annotations

import re


def _normalize(s: str) -> str:
    if not s:
        return ""
    t = s.strip().lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[\-_/]+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # 去掉末尾复数 s（"tangents" -> "tangent"），但保留以 ss 结尾的词
    tokens = t.split(" ")
    tokens = [
        w[:-1] if (len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us")) else w
        for w in tokens
    ]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Subtopic → formulas
# Keys are the raw English subtopic names used by the grader; we normalize at
# lookup time so spelling variations like "Tangents and Normals" still match.
# ---------------------------------------------------------------------------
_SUBTOPIC_FORMULAS: dict[str, list[str]] = {
    # ---------- Quadratics ----------
    "completing the square": [
        r"$ax^2+bx+c = a\left(x+\tfrac{b}{2a}\right)^2 + c - \tfrac{b^2}{4a}$",
    ],
    "discriminant": [
        r"$\Delta = b^2 - 4ac$",
        r"$\Delta>0$ 两实根，$\Delta=0$ 重根，$\Delta<0$ 无实根",
    ],
    "quadratic equations and discriminants": [
        r"$x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$",
        r"$\Delta = b^2 - 4ac$",
    ],
    "quadratic formula": [
        r"$x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$",
    ],
    "quadratic inequalities": [
        r"$ax^2+bx+c>0 \iff$ 两根之外 (a>0)",
    ],
    "simultaneous equations": [
        r"联立代入：$y=f(x)$ 代入第二式，化为一元方程",
    ],

    # ---------- Functions ----------
    "domain and range": [
        r"$f:\,x\mapsto y,\ x\in D$，值域 $R=\{f(x):x\in D\}$",
    ],
    "composite functions": [
        r"$(f\circ g)(x) = f(g(x))$",
    ],
    "inverse functions": [
        r"$f(f^{-1}(x)) = x$",
        r"$y=f(x)\ \Leftrightarrow\ x=f^{-1}(y)$",
    ],
    "graph transformations": [
        r"$y=f(x)+a$ 上移 $a$；$y=f(x-a)$ 右移 $a$",
        r"$y=af(x)$ 纵向拉伸 $a$；$y=f(ax)$ 横向压缩 $1/a$",
    ],
    "modulus functions": [
        r"$|x|=\sqrt{x^2}$；$|f(x)|=k \Rightarrow f(x)=\pm k$",
    ],

    # ---------- Coordinate geometry ----------
    "equations of lines": [
        r"$y-y_1 = m(x-x_1)$",
        r"斜率 $m = \dfrac{y_2-y_1}{x_2-x_1}$",
    ],
    "parallel and perpendicular": [
        r"平行：$m_1=m_2$；垂直：$m_1 m_2 = -1$",
    ],
    "midpoint and distance": [
        r"中点 $M=\left(\tfrac{x_1+x_2}{2},\tfrac{y_1+y_2}{2}\right)$",
        r"距离 $d=\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}$",
    ],
    "equation of circle": [
        r"$(x-a)^2+(y-b)^2=r^2$",
        r"一般式：$x^2+y^2+Dx+Ey+F=0$",
    ],
    "tangent to circle": [
        r"切线 $\perp$ 半径，且圆心到切线距离 $=r$",
    ],
    "perpendicular bisector": [
        r"过中点 $M$ 且斜率为 $-1/m$ 的直线",
    ],

    # ---------- Circular measure ----------
    "radian conversion": [
        r"$\pi\text{ rad} = 180^{\circ}$",
    ],
    "arc length": [
        r"$s = r\theta$（$\theta$ 为弧度）",
    ],
    "sector area": [
        r"$A = \tfrac{1}{2}r^2\theta$",
    ],
    "segment area": [
        r"$A = \tfrac{1}{2}r^2(\theta - \sin\theta)$",
    ],

    # ---------- Trigonometry ----------
    "trig ratios": [
        r"$\sin\theta = \tfrac{\text{opp}}{\text{hyp}},\ \cos\theta = \tfrac{\text{adj}}{\text{hyp}},\ \tan\theta = \tfrac{\text{opp}}{\text{adj}}$",
    ],
    "trig identities basic": [
        r"$\sin^2\theta + \cos^2\theta = 1$",
        r"$\tan\theta = \dfrac{\sin\theta}{\cos\theta}$",
    ],
    "trig identities": [
        r"$\sin^2\theta + \cos^2\theta = 1$",
        r"$1+\tan^2\theta = \sec^2\theta$",
        r"$1+\cot^2\theta = \csc^2\theta$",
    ],
    "trig equations": [
        r"$\sin\theta = k \Rightarrow \theta = \sin^{-1}k + 2\pi n$ 或 $\pi - \sin^{-1}k + 2\pi n$",
    ],
    "double angle formulae": [
        r"$\sin 2\theta = 2\sin\theta\cos\theta$",
        r"$\cos 2\theta = \cos^2\theta - \sin^2\theta = 1-2\sin^2\theta$",
    ],
    "addition formulae": [
        r"$\sin(A\pm B)=\sin A\cos B\pm\cos A\sin B$",
        r"$\cos(A\pm B)=\cos A\cos B\mp\sin A\sin B$",
    ],
    "r formula": [
        r"$a\sin\theta + b\cos\theta = R\sin(\theta+\alpha),\ R=\sqrt{a^2+b^2},\ \tan\alpha=b/a$",
    ],

    # ---------- Series ----------
    "binomial expansion": [
        r"$(1+x)^n = \displaystyle\sum_{k=0}^{n}\binom{n}{k}x^k$",
        r"$\binom{n}{k} = \dfrac{n!}{k!(n-k)!}$",
    ],
    "arithmetic progression": [
        r"$u_n = a + (n-1)d$",
        r"$S_n = \tfrac{n}{2}\,[2a + (n-1)d]$",
    ],
    "geometric progression": [
        r"$u_n = ar^{\,n-1}$",
        r"$S_n = \dfrac{a(1-r^n)}{1-r}\ (r\neq 1)$",
    ],
    "sum to infinity": [
        r"$S_\infty = \dfrac{a}{1-r},\ |r|<1$",
    ],

    # ---------- Differentiation ----------
    "differentiation from first principles": [
        r"$f'(x) = \lim_{h\to 0}\dfrac{f(x+h)-f(x)}{h}$",
    ],
    "power rule": [
        r"$\dfrac{d}{dx}\,x^n = n\,x^{\,n-1}$",
    ],
    "chain rule": [
        r"$\dfrac{d}{dx}f(g(x)) = f'(g(x))\,g'(x)$",
    ],
    "product rule": [
        r"$\dfrac{d}{dx}(uv) = u'v + uv'$",
    ],
    "quotient rule": [
        r"$\dfrac{d}{dx}\!\left(\dfrac{u}{v}\right) = \dfrac{u'v - uv'}{v^2}$",
    ],
    "tangent and normal": [
        r"切线：$y - y_0 = f'(x_0)(x-x_0)$",
        r"法线斜率 $= -\dfrac{1}{f'(x_0)}$",
    ],
    "stationary points": [
        r"驻点：$f'(x)=0$",
        r"二阶判别：$f''(x)>0$ 极小，$<0$ 极大",
    ],
    "increasing decreasing": [
        r"$f'(x)>0$ 递增；$f'(x)<0$ 递减",
    ],
    "connected rates of change": [
        r"$\dfrac{dy}{dt} = \dfrac{dy}{dx}\cdot\dfrac{dx}{dt}$",
    ],
    "second derivative": [
        r"$f''(x) = \dfrac{d}{dx}f'(x)$",
    ],
    "implicit differentiation": [
        r"$\dfrac{d}{dx}f(y) = f'(y)\,\dfrac{dy}{dx}$",
    ],
    "parametric differentiation": [
        r"$\dfrac{dy}{dx} = \dfrac{dy/dt}{dx/dt}$",
    ],

    # ---------- Integration ----------
    "reverse of differentiation": [
        r"$\displaystyle\int x^n\,dx = \dfrac{x^{\,n+1}}{n+1} + C\ (n\neq -1)$",
    ],
    "definite integrals": [
        r"$\displaystyle\int_a^b f(x)\,dx = F(b) - F(a)$",
    ],
    "area under curve": [
        r"$A = \displaystyle\int_a^b y\,dx$",
    ],
    "area between curves": [
        r"$A = \displaystyle\int_a^b [f(x)-g(x)]\,dx$",
    ],
    "volume of revolution": [
        r"$V = \pi\displaystyle\int_a^b y^2\,dx$（绕 $x$ 轴）",
    ],
    "integration by substitution": [
        r"$\displaystyle\int f(g(x))\,g'(x)\,dx = \int f(u)\,du$",
    ],
    "integration by parts": [
        r"$\displaystyle\int u\,dv = uv - \int v\,du$",
    ],
    "trig integration": [
        r"$\displaystyle\int \sin x\,dx = -\cos x + C$",
        r"$\displaystyle\int \cos x\,dx = \sin x + C$",
        r"$\displaystyle\int \sec^2 x\,dx = \tan x + C$",
    ],

    # ---------- Exponentials & logarithms ----------
    "exponential functions": [
        r"$\dfrac{d}{dx}e^{\,x} = e^{\,x}$，$\displaystyle\int e^{\,x}\,dx = e^{\,x}+C$",
    ],
    "logarithm laws": [
        r"$\log(ab) = \log a + \log b$",
        r"$\log(a^n) = n\log a$",
        r"换底：$\log_a b = \dfrac{\ln b}{\ln a}$",
    ],
    "natural logarithm": [
        r"$\dfrac{d}{dx}\ln x = \dfrac{1}{x}$，$\displaystyle\int \dfrac{1}{x}\,dx = \ln|x|+C$",
    ],
    "solving exponential equations": [
        r"$a^x = b \Rightarrow x = \log_a b$",
    ],

    # ---------- Vectors ----------
    "vector magnitude": [
        r"$|\mathbf{a}| = \sqrt{a_1^2+a_2^2+a_3^2}$",
    ],
    "scalar product": [
        r"$\mathbf{a}\cdot\mathbf{b} = |\mathbf{a}||\mathbf{b}|\cos\theta$",
        r"$\mathbf{a}\cdot\mathbf{b} = a_1b_1+a_2b_2+a_3b_3$",
    ],
    "dot product": [
        r"$\mathbf{a}\cdot\mathbf{b} = a_1b_1+a_2b_2+a_3b_3$",
    ],
    "vector equation of line": [
        r"$\mathbf{r} = \mathbf{a} + t\mathbf{d}$",
    ],

    # ---------- Numerical methods ----------
    "iteration": [
        r"$x_{n+1} = g(x_n)$；收敛条件 $|g'(x)|<1$",
    ],
    "trapezium rule": [
        r"$\displaystyle\int_a^b f(x)\,dx \approx \tfrac{h}{2}\left[y_0+y_n+2(y_1+\dots+y_{n-1})\right]$",
    ],

    # ---------- Probability & statistics ----------
    "probability": [
        r"$P(A\cup B) = P(A)+P(B)-P(A\cap B)$",
        r"$P(A|B) = \dfrac{P(A\cap B)}{P(B)}$",
    ],
    "conditional probability": [
        r"$P(A|B) = \dfrac{P(A\cap B)}{P(B)}$",
    ],
    "permutations and combinations": [
        r"$^nP_r = \dfrac{n!}{(n-r)!}$",
        r"$^nC_r = \dbinom{n}{r} = \dfrac{n!}{r!(n-r)!}$",
    ],
    "binomial distribution": [
        r"$X\sim B(n,p),\ P(X=r) = \dbinom{n}{r} p^r(1-p)^{n-r}$",
        r"$E(X)=np,\ \mathrm{Var}(X)=np(1-p)$",
    ],
    "normal distribution": [
        r"$X\sim N(\mu,\sigma^2)$；标准化 $Z=\dfrac{X-\mu}{\sigma}$",
    ],
    "poisson distribution": [
        r"$P(X=r) = e^{-\lambda}\dfrac{\lambda^r}{r!}$",
        r"$E(X)=\mathrm{Var}(X)=\lambda$",
    ],
    "mean and variance": [
        r"$\bar{x} = \dfrac{\sum x}{n},\ \mathrm{Var}(x) = \dfrac{\sum x^2}{n} - \bar{x}^2$",
    ],

    # ---------- Mechanics ----------
    "kinematics": [
        r"$v = u + at$",
        r"$s = ut + \tfrac{1}{2}at^2$",
        r"$v^2 = u^2 + 2as$",
    ],
    "newtons second law": [
        r"$F = ma$",
    ],
    "friction": [
        r"$F = \mu R$（最大静摩擦 $\mu_s R$）",
    ],
    "work energy power": [
        r"$W = Fs\cos\theta$",
        r"$KE = \tfrac{1}{2}mv^2$，$PE = mgh$",
        r"$P = Fv$",
    ],
}


# ---------------------------------------------------------------------------
# Topic (大节) → formulas —— subtopic 命中失败时的兜底
# ---------------------------------------------------------------------------
_TOPIC_FORMULAS: dict[str, list[str]] = {
    "quadratics": [
        r"$x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$",
        r"$\Delta = b^2 - 4ac$",
    ],
    "functions": [
        r"$(f\circ g)(x) = f(g(x))$",
        r"$f(f^{-1}(x)) = x$",
    ],
    "coordinate geometry": [
        r"$y-y_1 = m(x-x_1)$",
        r"$(x-a)^2+(y-b)^2=r^2$",
    ],
    "circular measure": [
        r"$s=r\theta$，$A=\tfrac{1}{2}r^2\theta$",
    ],
    "trigonometry": [
        r"$\sin^2\theta+\cos^2\theta=1$",
        r"$\sin 2\theta = 2\sin\theta\cos\theta$",
    ],
    "series": [
        r"$S_n^{AP}=\tfrac{n}{2}[2a+(n-1)d]$",
        r"$S_n^{GP}=\dfrac{a(1-r^n)}{1-r}$",
    ],
    "differentiation": [
        r"$\dfrac{d}{dx}x^n = nx^{n-1}$",
        r"$\dfrac{d}{dx}f(g(x)) = f'(g(x))g'(x)$",
    ],
    "integration": [
        r"$\displaystyle\int x^n\,dx = \dfrac{x^{n+1}}{n+1}+C$",
        r"$\displaystyle\int u\,dv = uv - \int v\,du$",
    ],
    "vectors": [
        r"$\mathbf{a}\cdot\mathbf{b} = |\mathbf{a}||\mathbf{b}|\cos\theta$",
        r"$\mathbf{r} = \mathbf{a} + t\mathbf{d}$",
    ],
    "probability": [
        r"$P(A\cup B)=P(A)+P(B)-P(A\cap B)$",
    ],
    "statistics": [
        r"$\bar{x} = \dfrac{\sum x}{n}$",
    ],
    "mechanics": [
        r"$F = ma$",
        r"$v = u+at$",
    ],
}


# 预归一化字典，加速运行时查表
_SUBTOPIC_NORM: dict[str, list[str]] = {
    _normalize(k): v for k, v in _SUBTOPIC_FORMULAS.items()
}
_TOPIC_NORM: dict[str, list[str]] = {
    _normalize(k): v for k, v in _TOPIC_FORMULAS.items()
}


def lookup_formulas(subtopic: str = "", topic: str = "", chapter: str = "") -> list[str]:
    """
    按 subtopic → topic 依次匹配官方公式。全部未命中返回空列表。
    """
    sub_key = _normalize(subtopic)
    if sub_key and sub_key in _SUBTOPIC_NORM:
        return list(_SUBTOPIC_NORM[sub_key])

    # 部分匹配：subtopic 是库里某 key 的子串（或反之）
    if sub_key:
        for k, v in _SUBTOPIC_NORM.items():
            if k in sub_key or sub_key in k:
                return list(v)

    top_key = _normalize(topic)
    if top_key and top_key in _TOPIC_NORM:
        return list(_TOPIC_NORM[top_key])
    if top_key:
        for k, v in _TOPIC_NORM.items():
            if k in top_key or top_key in k:
                return list(v)

    return []
