#pragma once
#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>

struct Distribution {
    std::vector<double> model, sampling;
    std::vector<int> best;
    double entropy = 0;
    Distribution(const float* logits, int n, double temperature) : model(n), sampling(n), best(n) {
        int highest = int(std::max_element(logits, logits+n)-logits);
        double a = 0, b = 0;
        for (int i = 0; i < n; ++i) {
            if (std::isnan(logits[i]) || logits[i] == INFINITY || !std::isfinite(logits[highest]))
                throw std::runtime_error("Invalid model logits");
            double delta = double(logits[i])-logits[highest];
            a += model[i] = std::exp(delta);
            if (temperature > 0) b += sampling[i] = std::exp(delta/temperature);
        }
        for (int i = 0; i < n; ++i) {
            model[i] /= a;
            sampling[i] = temperature > 0 ? sampling[i]/b : double(i == highest);
            if (model[i] > 0) entropy -= model[i]*std::log2(model[i]);
        }
        std::iota(best.begin(), best.end(), 0);
        size_t k = std::min<size_t>(5, best.size());
        std::partial_sort(best.begin(), best.begin()+k, best.end(), [&](int l, int r) {
            return logits[l] == logits[r] ? l < r : logits[l] > logits[r];
        });
        best.resize(k);
    }
    int draw(std::mt19937& rng) const {
        // Use the same uniform variate on MSVC and MinGW.
        double u = (double(rng()) + 0.5) / 4294967296.0, cumulative = 0;
        int last = best.front();
        for (size_t i = 0; i < sampling.size(); ++i) {
            cumulative += sampling[i];
            if (sampling[i] > 0) last = int(i);
            if (u < cumulative) return int(i);
        }
        return last;
    }
};
