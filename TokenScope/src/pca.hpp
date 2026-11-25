#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <vector>

using Vector = std::vector<float>;
using Point = std::array<float, 3>;

inline Vector unit(Vector v) {
    double length2 = std::inner_product(v.begin(), v.end(), v.begin(), 0.0);
    if (length2 > 0.0) {
        const float scale = float(1.0 / std::sqrt(length2));
        for (float &x : v) x *= scale;
    }
    return v;
}

// Fit once in the small token-by-token Gram matrix. All later tokens and
// intermediate residuals use this same centering vector and these axes.
class Projection {
    std::vector<double> mean;
    std::array<std::vector<double>, 3> axes;
public:
    Point variance{};
    explicit Projection(const std::vector<Vector>& rows) : mean(rows.at(0).size()) {
        const int n = int(rows.size()), d = int(mean.size());
        std::vector<std::vector<double>> x(n, std::vector<double>(d));
        for (int i = 0; i < n; ++i) {
            if (int(rows[i].size()) != d) throw std::runtime_error("Mixed vector widths");
            Vector u = unit(rows[i]);
            for (int j = 0; j < d; ++j) { x[i][j] = u[j]; mean[j] += u[j] / double(n); }
        }
        for (auto& row : x) for (int j = 0; j < d; ++j) row[j] -= mean[j];
        std::vector<double> g(n*n), v(n*n);
        double total = 0;
        for (int i = 0; i < n; ++i) {
            v[i*n+i] = 1;
            for (int j = 0; j <= i; ++j)
                g[j*n+i] = g[i*n+j] = std::inner_product(x[i].begin(), x[i].end(), x[j].begin(), 0.0);
            total += g[i*n+i];
        }
        // Cyclic Jacobi rotations diagonalize this real symmetric matrix.
        for (int sweep = 0; sweep < 48; ++sweep) {
            double largest = 0;
            for (int p = 0; p < n; ++p) for (int q = p+1; q < n; ++q) {
                double off = g[p*n+q];
                largest = std::max(largest, std::abs(off));
                if (std::abs(off) <= 1e-13 * std::max(1.0, total)) continue;
                double tau = (g[q*n+q] - g[p*n+p]) / (2.0*off);
                double t = std::copysign(1.0, tau) / (std::abs(tau) + std::hypot(1.0, tau));
                double c = 1.0 / std::hypot(1.0, t), s = t*c;
                g[p*n+p] -= t*off; g[q*n+q] += t*off; g[p*n+q] = g[q*n+p] = 0;
                for (int k = 0; k < n; ++k) {
                    if (k != p && k != q) {
                        double a = g[k*n+p], b = g[k*n+q];
                        g[k*n+p] = g[p*n+k] = c*a-s*b;
                        g[k*n+q] = g[q*n+k] = s*a+c*b;
                    }
                    double a = v[k*n+p], b = v[k*n+q];
                    v[k*n+p] = c*a-s*b; v[k*n+q] = s*a+c*b;
                }
            }
            if (largest <= 1e-13 * std::max(1.0, total)) break;
        }
        std::vector<int> order(n);
        std::iota(order.begin(), order.end(), 0);
        std::stable_sort(order.begin(), order.end(), [&](int a, int b){ return g[a*n+a] > g[b*n+b]; });
        for (int k = 0; k < 3; ++k) {
            axes[k].assign(d, 0);
            if (k >= n) continue;
            int col = order[k];
            double ev = g[col*n+col];
            if (ev <= 1e-10 * std::max(1.0, total)) continue;
            variance[k] = float(ev/total);
            for (int i = 0; i < n; ++i) for (int j = 0; j < d; ++j)
                axes[k][j] += v[i*n+col]*x[i][j]/std::sqrt(ev);
            auto pivot = std::max_element(axes[k].begin(), axes[k].end(), [](double a,double b){return std::abs(a)<std::abs(b);});
            if (pivot != axes[k].end() && *pivot < 0) for (double& a : axes[k]) a = -a;
        }
    }
    Point project(const Vector& row) const {
        if (row.size() != mean.size()) throw std::runtime_error("Projection width mismatch");
        Vector u = unit(row);
        Point p{};
        for (int k = 0; k < 3; ++k) {
            double pc = 0;
            for (size_t j = 0; j < u.size(); ++j) pc += axes[k][j]*(u[j]-mean[j]);
            p[k] = float(pc);
        }
        return p;
    }
};
