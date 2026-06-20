"""
CIE 9709 Mathematics A-Level 详细知识点分类体系

每个 Paper 的章节严格按照 CIE 大纲拆分，不合并。
用于爬虫入库打标签和练习模式筛选。
"""

# 难度等级
DIFFICULTY_LEVELS = {
    "low": {"label": "低", "range": (1, 2), "description": "基础题，直接套用公式/定义"},
    "medium": {"label": "中", "range": (3, 3), "description": "需要多步推理或综合运用"},
    "high": {"label": "高", "range": (4, 5), "description": "综合题、证明题、建模题"},
}

# ============================================================================
# Paper 1: Pure Mathematics 1 (AS)
# ============================================================================
PAPER_1_TOPICS = {
    "quadratics": {
        "name": "Quadratics",
        "name_cn": "二次函数与方程",
        "subtopics": [
            "completing_the_square",          # 配方法
            "discriminant",                    # 判别式
            "quadratic_inequalities",          # 二次不等式
            "simultaneous_equations",          # 联立方程
            "quadratic_graphs",                # 二次函数图像
        ],
    },
    "functions": {
        "name": "Functions",
        "name_cn": "函数",
        "subtopics": [
            "domain_and_range",                # 定义域与值域
            "composite_functions",             # 复合函数
            "inverse_functions",               # 反函数
            "graph_transformations",           # 图像变换 (平移/伸缩/反射)
            "modulus_functions",               # 绝对值函数 (AS level basic)
        ],
    },
    "coordinate_geometry": {
        "name": "Coordinate Geometry",
        "name_cn": "坐标几何",
        "subtopics": [
            "equations_of_lines",              # 直线方程
            "parallel_and_perpendicular",      # 平行与垂直
            "midpoint_and_distance",           # 中点与距离
            "equation_of_circle",              # 圆的方程
            "tangent_to_circle",               # 圆的切线
            "intersection_of_line_and_circle", # 直线与圆的交点
            "perpendicular_bisector",          # 垂直平分线
        ],
    },
    "circular_measure": {
        "name": "Circular Measure",
        "name_cn": "弧度制",
        "subtopics": [
            "radian_conversion",               # 角度弧度转换
            "arc_length",                      # 弧长
            "sector_area",                     # 扇形面积
            "segment_area",                    # 弓形面积
            "perimeter_problems",              # 周长综合题
        ],
    },
    "trigonometry_p1": {
        "name": "Trigonometry",
        "name_cn": "三角函数",
        "subtopics": [
            "trig_ratios",                     # 三角比
            "trig_identities_basic",           # 基本恒等式 (sin²+cos²=1, tanθ=sinθ/cosθ)
            "trig_equations",                  # 三角方程求解
            "trig_graphs",                     # 三角函数图像
            "trig_transformations",            # 三角函数图像变换
        ],
    },
    "series": {
        "name": "Series",
        "name_cn": "数列与级数",
        "subtopics": [
            "binomial_expansion",              # 二项式展开
            "arithmetic_progression",          # 等差数列
            "geometric_progression",           # 等比数列
            "sum_to_infinity",                 # 无穷等比级数求和
            "convergence",                     # 收敛条件
        ],
    },
    "differentiation_p1": {
        "name": "Differentiation",
        "name_cn": "微分",
        "subtopics": [
            "differentiation_from_first_principles",  # 第一性原理求导
            "power_rule",                      # 幂函数求导
            "tangent_and_normal",              # 切线与法线
            "stationary_points",               # 驻点 (极值)
            "increasing_decreasing",           # 递增递减
            "connected_rates_of_change",       # 相关变化率
            "second_derivative",               # 二阶导数
        ],
    },
    "integration_p1": {
        "name": "Integration",
        "name_cn": "积分",
        "subtopics": [
            "reverse_of_differentiation",      # 不定积分
            "definite_integrals",              # 定积分
            "area_under_curve",                # 曲线下面积
            "area_between_curves",             # 两曲线间面积
            "volume_of_revolution",            # 旋转体体积
        ],
    },
}

# ============================================================================
# Paper 2: Pure Mathematics 2 (AS) — 部分地区使用
# ============================================================================
PAPER_2_TOPICS = {
    "algebra_p2": {
        "name": "Algebra",
        "name_cn": "代数",
        "subtopics": [
            "modulus_functions",               # 绝对值函数
            "modulus_equations",                # 绝对值方程
            "modulus_inequalities",            # 绝对值不等式
            "polynomial_division",             # 多项式除法
            "remainder_theorem",               # 余数定理
            "factor_theorem",                  # 因式定理
        ],
    },
    "logarithmic_and_exponential_p2": {
        "name": "Logarithmic and Exponential Functions",
        "name_cn": "对数与指数函数",
        "subtopics": [
            "laws_of_logarithms",              # 对数运算法则
            "exponential_equations",           # 指数方程
            "logarithmic_equations",           # 对数方程
            "exponential_modelling",           # 指数建模
            "linear_law",                      # 线性化 (ln 变换)
        ],
    },
    "trigonometry_p2": {
        "name": "Trigonometry",
        "name_cn": "三角函数 (进阶)",
        "subtopics": [
            "double_angle_formulae",           # 二倍角公式
            "addition_formulae",               # 和差角公式
            "trig_identities_advanced",        # 高级恒等式
            "proving_trig_identities",         # 证明三角恒等式
        ],
    },
    "differentiation_p2": {
        "name": "Differentiation",
        "name_cn": "微分 (进阶)",
        "subtopics": [
            "chain_rule",                      # 链式法则
            "product_rule",                    # 乘法法则
            "quotient_rule",                   # 商法则
            "implicit_differentiation",        # 隐函数求导
            "differentiation_of_trig",         # 三角函数求导
            "differentiation_of_exponential",  # 指数函数求导
            "differentiation_of_ln",           # 对数函数求导
        ],
    },
    "integration_p2": {
        "name": "Integration",
        "name_cn": "积分 (进阶)",
        "subtopics": [
            "integration_of_exponential",      # 指数函数积分
            "integration_of_1_over_x",         # 1/x 积分 (ln)
            "integration_of_trig",             # 三角函数积分
            "trapezium_rule",                  # 梯形法则 (数值积分)
        ],
    },
    "numerical_methods_p2": {
        "name": "Numerical Methods",
        "name_cn": "数值方法",
        "subtopics": [
            "sign_change_method",              # 符号变化法 (验证根的存在)
            "iterative_methods",               # 迭代法
            "convergence_of_iterative",        # 迭代收敛性
        ],
    },
}

# ============================================================================
# Paper 3: Pure Mathematics 3 (A2)
# ============================================================================
PAPER_3_TOPICS = {
    "algebra_p3": {
        "name": "Algebra",
        "name_cn": "代数 (A2)",
        "subtopics": [
            "partial_fractions",               # 部分分式
            "modulus_functions_p3",             # 绝对值函数
            "modulus_inequalities_p3",          # 绝对值不等式
            "binomial_expansion_fractional",    # 分数/负指数二项展开
        ],
    },
    "logarithmic_and_exponential_p3": {
        "name": "Logarithmic and Exponential Functions",
        "name_cn": "对数与指数函数 (A2)",
        "subtopics": [
            "logarithmic_equations_p3",        # 对数方程
            "exponential_modelling_p3",        # 指数建模
            "linear_law_p3",                   # 线性化
        ],
    },
    "trigonometry_p3": {
        "name": "Trigonometry",
        "name_cn": "三角函数 (A2)",
        "subtopics": [
            "double_angle_formulae",           # 二倍角公式
            "addition_formulae",               # 和差角公式
            "r_formula",                       # R·sin(θ+α) / R·cos(θ+α)
            "proving_trig_identities_p3",      # 证明三角恒等式
            "inverse_trig_functions",          # 反三角函数
        ],
    },
    "differentiation_p3": {
        "name": "Differentiation",
        "name_cn": "微分 (A2)",
        "subtopics": [
            "chain_rule",
            "product_rule",
            "quotient_rule",
            "implicit_differentiation",
            "parametric_differentiation",      # 参数方程求导
            "differentiation_of_trig",
            "differentiation_of_exponential",
            "differentiation_of_ln",
        ],
    },
    "integration_p3": {
        "name": "Integration",
        "name_cn": "积分 (A2)",
        "subtopics": [
            "integration_by_parts",            # 分部积分
            "integration_by_substitution",     # 换元积分
            "integration_using_partial_fractions",  # 部分分式积分
            "integration_of_trig_p3",          # 三角函数积分 (进阶)
            "volume_of_revolution_p3",         # 旋转体体积 (进阶)
        ],
    },
    "numerical_methods_p3": {
        "name": "Numerical Methods",
        "name_cn": "数值方法 (A2)",
        "subtopics": [
            "sign_change_method",
            "iterative_methods",
            "convergence_of_iterative",
            "trapezium_rule",
        ],
    },
    "differential_equations": {
        "name": "Differential Equations",
        "name_cn": "微分方程",
        "subtopics": [
            "separation_of_variables",         # 分离变量法
            "first_order_ode",                 # 一阶常微分方程
            "modelling_with_ode",              # 微分方程建模
            "logistic_growth",                 # 逻辑斯蒂增长模型
        ],
    },
    "vectors_p3": {
        "name": "Vectors",
        "name_cn": "向量",
        "subtopics": [
            "vector_equation_of_line",         # 直线的向量方程
            "scalar_product",                  # 数量积 (点积)
            "perpendicular_vectors",           # 垂直向量
            "intersection_of_lines",           # 直线交点
            "angle_between_lines",             # 两直线夹角
            "point_to_line_distance",          # 点到直线距离
            "equation_of_plane",               # 平面方程
            "reflection_in_line",              # 直线的反射
        ],
    },
    "complex_numbers": {
        "name": "Complex Numbers",
        "name_cn": "复数",
        "subtopics": [
            "complex_arithmetic",              # 复数四则运算
            "modulus_argument_form",            # 模-辐角形式
            "polar_form",                      # 极坐标形式
            "argand_diagram",                  # 阿甘图 (Argand diagram)
            "loci_in_argand_diagram",          # 阿甘图上的轨迹
            "complex_roots_of_equations",      # 方程的复数根
        ],
    },
}

# ============================================================================
# Paper 4: Mechanics (A2)
# ============================================================================
PAPER_4_TOPICS = {
    "forces_and_equilibrium": {
        "name": "Forces and Equilibrium",
        "name_cn": "力与平衡",
        "subtopics": [
            "resolving_forces",                # 力的分解
            "resultant_force",                 # 合力
            "equilibrium_of_particle",         # 质点平衡
            "friction",                        # 摩擦力
            "inclined_plane_forces",           # 斜面上的力
            "triangle_of_forces",              # 力的三角形
        ],
    },
    "kinematics": {
        "name": "Kinematics of Motion in a Straight Line",
        "name_cn": "直线运动学",
        "subtopics": [
            "displacement_velocity_acceleration",  # 位移、速度、加速度
            "suvat_equations",                 # suvat 公式 (匀加速运动)
            "velocity_time_graphs",            # 速度-时间图
            "displacement_time_graphs",        # 位移-时间图
            "vertical_motion_under_gravity",   # 竖直方向自由落体/抛体
            "variable_acceleration",           # 变加速运动 (微积分法)
            "calculus_based_kinematics",        # 用微积分求 v, s, a
        ],
    },
    "newtons_laws": {
        "name": "Newton's Laws of Motion",
        "name_cn": "牛顿运动定律",
        "subtopics": [
            "newtons_second_law",              # F = ma
            "motion_on_inclined_plane",        # 斜面上的运动
            "connected_particles_pulley",      # 滑轮连接体
            "connected_particles_tow_bar",     # 拖杆/绳连接 (车+拖车)
            "lift_problems",                   # 电梯问题
        ],
    },
    "energy_work_power": {
        "name": "Energy, Work and Power",
        "name_cn": "能量、功和功率",
        "subtopics": [
            "work_done",                       # 功
            "kinetic_energy",                  # 动能
            "potential_energy",                # 势能 (重力势能)
            "work_energy_theorem",             # 动能定理
            "conservation_of_energy",          # 能量守恒
            "power",                           # 功率
            "driving_force",                   # 驱动力
            "resistance_force",                # 阻力
        ],
    },
    "momentum": {
        "name": "Momentum",
        "name_cn": "动量",
        "subtopics": [
            "conservation_of_momentum",        # 动量守恒
            "collision",                       # 碰撞
            "rebound",                         # 反弹
            "impulse",                         # 冲量
        ],
    },
}

# ============================================================================
# Paper 5: Probability & Statistics 1 (AS)
# ============================================================================
PAPER_5_TOPICS = {
    "representation_of_data": {
        "name": "Representation of Data",
        "name_cn": "数据表示",
        "subtopics": [
            "stem_and_leaf_diagram",           # 茎叶图
            "histogram",                       # 直方图 (不等宽)
            "cumulative_frequency",            # 累积频率
            "box_and_whisker_plot",            # 箱线图
        ],
    },
    "measures_of_central_tendency": {
        "name": "Measures of Central Tendency",
        "name_cn": "集中趋势度量",
        "subtopics": [
            "mean",                            # 平均数
            "median",                          # 中位数
            "mode",                            # 众数
            "mean_from_frequency_table",       # 频率表求均值
            "coded_data_mean",                 # 编码数据求均值
        ],
    },
    "measures_of_variation": {
        "name": "Measures of Variation",
        "name_cn": "离散程度度量",
        "subtopics": [
            "range",                           # 全距
            "interquartile_range",             # 四分位距
            "variance",                        # 方差
            "standard_deviation",              # 标准差
            "coded_data_variance",             # 编码数据求方差
            "summary_statistics",              # Σx, Σx² 求统计量
        ],
    },
    "permutations_and_combinations": {
        "name": "Permutations and Combinations",
        "name_cn": "排列与组合",
        "subtopics": [
            "permutations",                    # 排列 (有序)
            "combinations",                    # 组合 (无序)
            "arrangements_with_repetition",    # 含重复元素的排列
            "arrangements_with_restrictions",  # 有限制条件的排列
            "committee_selection",             # 委员会选取问题
        ],
    },
    "probability": {
        "name": "Probability",
        "name_cn": "概率",
        "subtopics": [
            "addition_rule",                   # 加法法则
            "multiplication_rule",             # 乘法法则
            "conditional_probability",         # 条件概率
            "independent_events",              # 独立事件
            "mutually_exclusive_events",       # 互斥事件
            "tree_diagrams",                   # 树形图
            "venn_diagrams",                   # 维恩图
        ],
    },
    "discrete_random_variables": {
        "name": "Discrete Random Variables",
        "name_cn": "离散随机变量",
        "subtopics": [
            "probability_distribution_table",  # 概率分布表
            "expectation",                     # 期望 E(X)
            "variance_of_drv",                 # 方差 Var(X)
        ],
    },
    "binomial_distribution": {
        "name": "Binomial Distribution",
        "name_cn": "二项分布",
        "subtopics": [
            "binomial_probability",            # B(n,p) 概率计算
            "binomial_mean_variance",          # 均值和方差
            "normal_approximation_to_binomial",  # 正态近似二项
        ],
    },
    "geometric_distribution": {
        "name": "Geometric Distribution",
        "name_cn": "几何分布",
        "subtopics": [
            "geometric_probability",           # Geo(p) 概率计算
            "geometric_mean",                  # 期望
        ],
    },
    "normal_distribution": {
        "name": "Normal Distribution",
        "name_cn": "正态分布",
        "subtopics": [
            "standardisation",                 # 标准化 Z = (X-μ)/σ
            "normal_probability",              # 正态概率计算
            "inverse_normal",                  # 逆正态 (已知概率求值)
            "find_mean_or_sd",                 # 已知概率求 μ 或 σ
        ],
    },
}

# ============================================================================
# Paper 6: Probability & Statistics 2 (A2)
# ============================================================================
PAPER_6_TOPICS = {
    "poisson_distribution": {
        "name": "Poisson Distribution",
        "name_cn": "泊松分布",
        "subtopics": [
            "poisson_probability",             # Po(λ) 概率计算
            "poisson_conditions",              # 泊松分布适用条件
            "sum_of_poisson",                  # 独立泊松变量之和
            "poisson_mean_variance",           # 均值和方差
            "normal_approximation_to_poisson", # 正态近似泊松
            "poisson_approximation_to_binomial",  # 泊松近似二项
        ],
    },
    "linear_combinations": {
        "name": "Linear Combinations of Random Variables",
        "name_cn": "随机变量的线性组合",
        "subtopics": [
            "expectation_of_linear_combination",   # E(aX+bY)
            "variance_of_linear_combination",      # Var(aX+bY)
            "sum_and_difference_of_normal",        # 正态变量的和与差
        ],
    },
    "continuous_random_variables": {
        "name": "Continuous Random Variables",
        "name_cn": "连续随机变量",
        "subtopics": [
            "probability_density_function",    # 概率密度函数 (PDF)
            "cumulative_distribution_function",  # 累积分布函数 (CDF)
            "expectation_of_crv",              # 期望
            "variance_of_crv",                 # 方差
            "median_of_crv",                   # 中位数
            "mode_of_crv",                     # 众数
        ],
    },
    "sampling_and_estimation": {
        "name": "Sampling and Estimation",
        "name_cn": "抽样与估计",
        "subtopics": [
            "unbiased_estimates",              # 无偏估计 (样本均值、方差)
            "sampling_distribution_of_mean",   # 样本均值的分布
            "central_limit_theorem",           # 中心极限定理
            "confidence_intervals",            # 置信区间
        ],
    },
    "hypothesis_testing": {
        "name": "Hypothesis Testing",
        "name_cn": "假设检验",
        "subtopics": [
            "z_test",                          # z 检验
            "one_tailed_test",                 # 单侧检验
            "two_tailed_test",                 # 双侧检验
            "type_I_error",                    # 第一类错误
            "type_II_error",                   # 第二类错误
            "hypothesis_test_binomial",        # 二项分布假设检验
            "hypothesis_test_poisson",         # 泊松分布假设检验
            "hypothesis_test_normal",          # 正态分布假设检验
        ],
    },
}

# ============================================================================
# 汇总：Paper → Topics 映射
# ============================================================================
PAPER_TOPICS = {
    1: PAPER_1_TOPICS,
    2: PAPER_2_TOPICS,
    3: PAPER_3_TOPICS,
    4: PAPER_4_TOPICS,
    5: PAPER_5_TOPICS,
    6: PAPER_6_TOPICS,
}

PAPER_INFO = {
    1: {"name": "Pure Mathematics 1", "level": "AS", "component": "pure_math"},
    2: {"name": "Pure Mathematics 2", "level": "AS", "component": "pure_math"},
    3: {"name": "Pure Mathematics 3", "level": "A2", "component": "pure_math"},
    4: {"name": "Mechanics",          "level": "A2", "component": "mechanics"},
    5: {"name": "Probability & Statistics 1", "level": "AS", "component": "statistics"},
    6: {"name": "Probability & Statistics 2", "level": "A2", "component": "statistics"},
}


def get_all_topics_flat(paper_num: "int | None" = None) -> list[dict]:
    """获取扁平化的知识点列表，用于 API 返回"""
    result = []
    papers = {paper_num: PAPER_TOPICS[paper_num]} if paper_num else PAPER_TOPICS

    for pnum, topics in papers.items():
        pinfo = PAPER_INFO[pnum]
        for topic_key, topic_data in topics.items():
            for sub in topic_data["subtopics"]:
                result.append({
                    "paper_num": pnum,
                    "paper_name": pinfo["name"],
                    "level": pinfo["level"],
                    "topic_key": topic_key,
                    "topic_name": topic_data["name"],
                    "topic_name_cn": topic_data["name_cn"],
                    "subtopic": sub,
                })
    return result


def get_topic_tree(paper_num: "int | None" = None) -> list[dict]:
    """获取树形结构的知识点，用于前端展示"""
    result = []
    papers = {paper_num: PAPER_TOPICS[paper_num]} if paper_num else PAPER_TOPICS

    for pnum, topics in papers.items():
        pinfo = PAPER_INFO[pnum]
        paper_node = {
            "paper_num": pnum,
            "paper_name": pinfo["name"],
            "level": pinfo["level"],
            "component": pinfo["component"],
            "topics": [],
        }
        for topic_key, topic_data in topics.items():
            paper_node["topics"].append({
                "key": topic_key,
                "name": topic_data["name"],
                "name_cn": topic_data["name_cn"],
                "subtopics": topic_data["subtopics"],
            })
        result.append(paper_node)
    return result
