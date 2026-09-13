# PayLens — Know the payment risk before you sign the deal

## Inspiration

A small business owner we spoke to described a moment that stuck with us: she won the biggest contract of her career, and it nearly closed her down. The deal was profitable on paper. It was also 60-day terms, no deposit, and three months of payroll she had to cover before a single dollar arrived.

That is the gap we built for. Every tool a small business can reach answers *"is this contract profitable?"*. Almost none answer the question that actually kills companies:

> **Can I survive the wait?**

Late payment is not an edge case in Australia — it is the operating condition. The federal Payment Times Reporting Register exists precisely because large buyers routinely stretch their small suppliers. But the register is a compliance artifact: tens of thousands of rows of reporting periods, published for transparency, unreadable at the moment a decision is actually made. The data that could warn a supplier already exists. It just never reaches the person holding the pen.

PayLens puts it there, **before the contract is signed**.

## What it does

You search for a prospective customer by name or ABN. PayLens pulls that company's real payment-behaviour history, estimates how likely they are to pay late, and asks you four things about the deal in front of you: contract value, your available cash, your monthly operating costs, and the terms on offer.

It returns one number out of 100, a risk level, and — the part we care about most — the *reason*:

> **82 / 100 · CRITICAL**
> The contract's net exposure is more than twice your available cash reserve.
> The estimated time until payment exceeds your current cash runway.
> Estimated operating costs during the waiting period exceed your cash reserve.

Then it lets you negotiate against it. A restructuring simulator recalculates the score live as you move upfront payment and payment terms, and solves for the smallest deposit that would pull the deal into a safer band — *"25% upfront would bring this to Moderate at 60-day terms."* That sentence is something a supplier can take into a negotiation on Monday morning.

## How we built it

The architecture splits on a deliberate line: **a model predicts the customer, arithmetic predicts the contract.**

```text
Payment Times Register  →  preprocessing  →  logistic regression  →  P(high delay)
                                                                          ↓
your contract inputs  →  deterministic exposure engine  →  score · reasons · simulator
```

### The customer model

We built a supervised training set from the data owner's canonical payment-times history — **72,900 company-period records**, condensed to **45,000 labelled training rows**. Each row is one company in one reporting period, described by nine features: the share of invoices paid within 30 / 31–60 / over 60 days, share paid within stated terms, a trend term, a volatility term, the company's percentile within its industry, how many periods it has reported, and the gap between its stated and actual payment terms.

The label is forward-looking, which matters more than the model choice:

$$y = \mathbb{1}\left[\text{pct\_paid\_over\_60}^{(t+1)} \geq 0.20\right]$$

We are not scoring how a company paid. We are predicting whether **next** period it tips into high delay — because that is the period your contract lives in.

A logistic regression carries it. The choice was not a compromise: an interpretable model is a *product requirement* here, since every number PayLens shows must be defensible to a user making a financial decision. Evaluated on a chronological hold-out (periods from Oct 2023 onward, never seen in training):

| Split | Rows | ROC-AUC | Precision | Recall |
|---|---|---|---|---|
| Train | 28,188 | 0.915 | 0.467 | 0.837 |
| Validation | 8,065 | 0.924 | 0.432 | 0.862 |
| **Test** | **7,775** | **0.925** | **0.460** | **0.846** |

We tuned toward recall on purpose. A false alarm costs a supplier one awkward conversation about a deposit. A miss costs them the payroll.

### The exposure engine

Everything downstream of the model is deterministic, auditable arithmetic. Given a contract, we derive:

$$E_{\text{net}} = V \cdot (1 - u) \qquad D_{\text{wait}} = d_{\text{delivery}} + d_{\text{terms}} + 30p$$

$$r_{\text{cash}} = \frac{E_{\text{net}}}{C} \qquad R_{\text{runway}} = \frac{C}{M} \qquad K_{\text{wait}} = \frac{M}{30} \cdot D_{\text{wait}}$$

where $V$ is contract value, $u$ the upfront fraction, $C$ available cash, $M$ monthly operating cost, and $p$ the model's delay probability — note that $p$ enters the *timeline*, stretching the expected wait by up to 30 days, not just the score.

Four sub-scores are each mapped to $[0, 100]$ — cash exposure piecewise-linearly through the breakpoints $r_{\text{cash}} \in \{0.5, 1, 2, 3\} \mapsto \{25, 50, 75, 100\}$, waiting-period risk by banding $D_{\text{wait}} / R_{\text{runway}}$, upfront protection as $100(1-u)$, and customer risk as $100p$ — then combined:

$$S = \sum_i w_i s_i, \qquad w = \begin{cases} 0.20 & \text{customer} \\ 0.40 & \text{cash exposure} \\ 0.20 & \text{waiting period} \\ 0.20 & \text{upfront} \end{cases}$$

clipped to $[0, 100]$ and banded: Low $\leq 30$, Moderate $\leq 55$, High $\leq 75$, Critical above.

The simulator inverts this. To find the minimum viable deposit we sweep $u$ in 5% increments and return the first structure that lands at or below the target band — a small search, but it turns a diagnosis into a negotiating position.

The app itself is Streamlit with hand-written HTML/CSS components, behind a service facade (`src/services.py`) that lets the whole UI run against either real data or demo fixtures by flipping one environment variable. **103 automated tests** cover the engines, state machine, formatting, and a full end-to-end journey through the real Streamlit runtime.

## Challenges we faced

**The inversion that would have shipped a lie.** Our model outputs $P(\text{high delay})$ — high is bad. But half the natural phrasings in finance run the other way (probability of payment, on-time rate), and early on a parameter named `payment_probability` was being handed a delay probability. The failure is silent and catastrophic: the worst-paying customers would have scored as the safest. We fixed it by making the naming convention a documented project rule, and now assert the *direction* of the relationship in tests — as $p$ rises, displayed risk must rise.

**Zeros that weren't zeros.** In the source register, a company reporting all six payment-time bands as zero is a company that filed nothing — not a company that pays everything instantly. Treating that as perfect behaviour would have manufactured thousands of flawless customers out of missing paperwork. Those rows are excluded as missing, and first-period companies with no trend or volatility history are median-imputed with an explicit missingness indicator.

**Splitting time, not rows.** A random train/test split leaks here: the same company appears in many periods, and the future leaks into the past. We split chronologically on `period_end` instead, so the test set is genuinely later than the training set. The metrics dropped from flattering to honest, which is the point.

**Two engines and a diverging truth.** We ended up with two risk implementations — one built for the UI's shape, one a standalone rule engine — and the simulator and the main analysis could quietly disagree. Rather than delete either, we routed everything through a single adapter so *one* engine is the source of truth for both the current deal and every simulated alternative. A comparison harness now checks they agree.

**Weighting the noisiest input.** The ML probability originally carried 30% of the score. But it is the one input we *infer* rather than observe, and at 30% a single model swing pushed deals a whole risk band. We cut it to 20% and moved that 10% to cash exposure — which is computed from numbers the user typed in and can verify. The effect is real and directional: our demo contract moved from 73 (High) to 82 (Critical), because a low-delay customer offering a deal 3.1× your cash reserve is still a deal that can sink you. The model informs the score; the arithmetic anchors it.

**The test harness that lied about the UI.** Streamlit's `AppTest` models every segmented control as multi-select, so our single-select payment-terms widget raised `TypeError: 'int' object is not iterable` — in the tests only; the browser was fine. We patched the harness rather than distort the app to suit it.

## What we learned

The hardest engineering in a risk product is not the model — it is **deciding what the model is allowed to decide.** Our best work this hackathon was subtractive: cutting the ML weight, refusing to let an inferred probability outrank an observed cash position, and writing down what PayLens explicitly does *not* predict (insolvency, default, profitability, legal enforceability).

We also learned that *transparency is a feature users can feel*. An unexplained 82 is noise. "Your net exposure is 3.1× your cash and you'll wait ~93 days on a 1.3-month runway" is something a person can act on, argue with, and take to a customer. Every score component in PayLens is traceable to a line of arithmetic and a number the user entered — and the weights live in one dictionary, in one file, quoted directly in the app's own methodology panel.

And a small practical one: put the service boundary in early. Because every data and model call goes through one facade, we swapped the entire backend from demo fixtures to 72,000 rows of real company history by changing a single default — with the UI, the tests, and the demo path all still working.

## What's next

- **Milestone payments and staged delivery** — modelling multiple payment events rather than one lump at the end, which is how most real contracts are actually rescued.
- **Calibrated probabilities and uncertainty bands**, so the UI can show *"11%, ±6"* instead of implying a precision the model does not have.
- **Scenario analysis** for partial, disputed, and delayed payment — the tail outcomes that matter most.
- **Exportable one-page reports** a supplier can attach to a negotiation email or take to a lender.
- **Model versioning and drift monitoring**, because payment behaviour in 2026 is not payment behaviour in 2021.

---

*PayLens is a decision-support prototype. It is not a credit rating, a financial guarantee, or legal advice — it is a way to see the cash-flow shape of a deal before you commit to it.*
