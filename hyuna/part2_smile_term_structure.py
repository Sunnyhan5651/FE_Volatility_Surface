# FE 3주차 2번 파트: 코스피200 smile/skew & term structure 사례
# 필요 데이터: opt.pkl/fut.pkl = kospi200_options_regular.csv / kospi200_futures_regular.csv 
import pandas as pd, numpy as np
o=pd.read_pickle('opt.pkl'); f=pd.read_pickle('fut.pkl')
o['date']=pd.to_datetime(o.BAS_DD); o['ltd']=pd.to_datetime(o.LAST_TRADING_DATE)
o['T']=(o.ltd-o.date).dt.days/365
# forward: futures settle for matching expiry (prefer KOSPI200 futures, then mini)
f=f.sort_values('PROD_NM')  # 미니 before 코스피 -> keep last = KOSPI200
fw=f.dropna(subset=['SETL_PRC']).drop_duplicates(['BAS_DD','EXPIRY_YM'],keep='last').set_index(['BAS_DD','EXPIRY_YM']).SETL_PRC
o=o.join(fw.rename('F'),on=['BAS_DD','EXPIRY_YM'])
o['F']=o.F.fillna(o.KOSPI200_SPOT_CLOSE)
o['m']=o.STRIKE/o.F
otm=o[((o.RGHT_TP_NM=='PUT')&(o.m<1))|((o.RGHT_TP_NM=='CALL')&(o.m>=1))]
otm=otm[(otm.ACC_OPNINT_QTY>0)&(otm.IMP_VOLT>5)&(otm.IMP_VOLT<150)&(otm['T']>0)]
otm.to_pickle('otm.pkl')
def iv_at(g,x):
    g=g.sort_values('m'); 
    if g.m.min()>x or g.m.max()<x: return np.nan
    return np.interp(x,g.m,g.IMP_VOLT)
rows=[]
for d,g in otm.groupby('BAS_DD'):
    exps=sorted(g[g['T']>7/365].EXPIRY_YM.unique())
    r={'BAS_DD':d}
    for i,e in enumerate(exps[:3]):
        ge=g[g.EXPIRY_YM==e]; r[f'atm{i}']=iv_at(ge,1.0); r[f'T{i}']=ge['T'].iloc[0]
        if i==0:
            r['iv90']=iv_at(ge,0.9); r['iv110']=iv_at(ge,1.1); r['F']=ge.F.iloc[0]
    rows.append(r)
ts=pd.DataFrame(rows)
s=pd.read_csv('/mnt/user-data/attachments/6e1f4750-56cc-58b4-a649-91072a6570d8/afd93598-kospi200_spot.csv',dtype={'BAS_DD':str})[['BAS_DD','KOSPI200_SPOT_CLOSE','FLUC_RT']]
ts=ts.merge(s,on='BAS_DD')
ts['skew90']=ts.iv90-ts.atm0; ts['skew110']=ts.iv110-ts.atm0; ts['ts_slope']=ts.atm2-ts.atm0
ts['rv20']=np.log(ts.KOSPI200_SPOT_CLOSE).diff().rolling(20).std()*np.sqrt(252)*100
ts.to_pickle('ts.pkl')
import pandas as pd, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from scipy.stats import norm; from scipy.optimize import brentq
fm.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family':'Noto Sans CJK JP','axes.unicode_minus':False,'font.size':12,
  'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#8a8984','axes.labelcolor':'#52514e',
  'xtick.color':'#52514e','ytick.color':'#52514e','axes.grid':True,'grid.color':'#e6e5e0','grid.linewidth':.8,
  'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','savefig.facecolor':'#fcfcfb'})
C={'calm':'#2a78d6','stress':'#eb6834'}; INK='#0b0b0b'; MUTE='#52514e'
otm=pd.read_pickle('otm.pkl'); ts=pd.read_pickle('ts.pkl')
CALM,STRESS='20251224','20260304'
lab={CALM:'평온: 2025-12-24',STRESS:'급락: 2026-03-04 (−11.9%)'}
def binned(g,step=0.02):
    g=g[g.m.between(0.72,1.28)].copy(); g['b']=(g.m/step).round()*step
    return g.groupby('b').IMP_VOLT.median().rolling(3,center=True,min_periods=1).median()
def pick(d,mind=30):
    g=otm[otm.BAS_DD==d]; e=sorted(g[g['T']*365>=mind].EXPIRY_YM.unique())[0]; return g[g.EXPIRY_YM==e],e
out={}
# --- 1. smile
fig,axs=plt.subplots(1,2,figsize=(13,5.2))
for d,k in [(CALM,'calm'),(STRESS,'stress')]:
    g,e=pick(d); b=binned(g); atm=np.interp(1,b.index,b.values)
    T=int(round(g['T'].iloc[0]*365)); out[d]={'exp':e,'T':T,'atm':atm,'iv90':np.interp(.9,b.index,b.values),'iv110':np.interp(1.1,b.index,b.values),'iv80':np.interp(.8,b.index,b.values)}
    tr=g[(g.ACC_TRDVOL>0)&g.m.between(.72,1.28)]
    for ax,norm_ in [(axs[0],False),(axs[1],True)]:
        y=tr.IMP_VOLT/(atm if norm_ else 1); yb=b/(atm if norm_ else 1)
        ax.scatter(tr.m,y,s=8,color=C[k],alpha=.18,lw=0)
        ax.plot(b.index,yb,color=C[k],lw=2.2,label=f"{lab[d]}  (만기 {e[:4]}.{e[4:]}, {T}일)")
for ax in axs: ax.axvline(1,color='#8a8984',lw=1,ls=(0,(3,3))); ax.set_xlabel('행사가 / 선물가격  (K/F)')
axs[0].set_ylabel('내재변동성 (%)'); axs[0].set_title('① 절대 수준: 위기 때 곡선 전체가 위로 이동',loc='left',color=INK,fontsize=13)
axs[1].set_ylabel('IV ÷ ATM IV'); axs[1].set_title('② 모양만 비교: ATM=1로 정규화',loc='left',color=INK,fontsize=13)
axs[1].axhline(1,color='#8a8984',lw=.8)
axs[0].legend(frameon=False,fontsize=10,loc='upper right')
fig.suptitle('코스피200 옵션 Volatility Skew — 평온한 날 vs 급락한 날',x=.01,ha='left',fontsize=15,color=INK,fontweight='bold')
fig.text(.01,.005,'자료: KRX 코스피200 옵션(정규) 일별 데이터, KRX 공표 내재변동성. 각 날짜에서 만기 30일 이상 중 가장 가까운 월물, OTM 옵션(K<F 풋, K≥F 콜). 점=거래된 종목, 선=0.02 구간 중앙값.',fontsize=8.5,color=MUTE)
plt.tight_layout(rect=(0,.03,1,.95)); plt.savefig('fig1_skew.png',dpi=200); plt.close()
# --- 2. term structure
fig,ax=plt.subplots(figsize=(11,5.2))
for d,k in [(CALM,'calm'),(STRESS,'stress')]:
    g=otm[otm.BAS_DD==d]; pts=[]
    for e,ge in g.groupby('EXPIRY_YM'):
        near=ge[ge.m.between(.95,1.05)]
        if len(near)<4 or not (near.m.min()<1<near.m.max()): continue
        b=binned(ge,0.01); pts.append((ge['T'].iloc[0]*365,np.interp(1,b.index,b.values),e))
    pts=sorted(pts); x,y,e=zip(*pts); out[d]['term']=pts
    ax.plot(x,y,'-',color=C[k],lw=2.2,label=lab[d]); ax.scatter(x,y,s=64,color=C[k],edgecolor='#fcfcfb',lw=2,zorder=3)
    ax.annotate(f'{y[0]:.0f}%',(x[0],y[0]),xytext=(8,6),textcoords='offset points',color=INK,fontsize=11)
    ax.annotate(f'{y[-1]:.0f}%',(x[-1],y[-1]),xytext=(6,6),textcoords='offset points',color=INK,fontsize=11)
ax.set_xlabel('잔존만기 (일)'); ax.set_ylabel('ATM 내재변동성 (%)')
ax.set_title('코스피200 ATM 변동성 기간구조 — 평온할 땐 우상향, 위기엔 역전',loc='left',fontsize=15,color=INK,fontweight='bold')
ax.legend(frameon=False); ax.set_ylim(0,None)
fig.text(.01,.01,'자료: KRX. ATM = K/F=1 지점의 내재변동성(OTM 옵션 IV를 보간). ATM 근처에 유효 호가가 있는 만기만 표시.',fontsize=8.5,color=MUTE)
plt.tight_layout(rect=(0,.03,1,1)); plt.savefig('fig2_term.png',dpi=200); plt.close()
# --- 3. time series
ts['date']=pd.to_datetime(ts.BAS_DD)
fig,(a1,a2)=plt.subplots(2,1,figsize=(13,6.6),sharex=True,gridspec_kw={'height_ratios':[1,1.2]})
a1.plot(ts.date,ts.KOSPI200_SPOT_CLOSE,color=INK,lw=1.6); a1.set_ylabel('코스피200')
a2.plot(ts.date,ts.atm0,color=C['stress'],lw=1.8,label='근월물 ATM IV')
a2.plot(ts.date,ts.atm2,color=C['calm'],lw=1.8,label='3번째 월물 ATM IV')
a2.fill_between(ts.date,ts.atm0,ts.atm2,where=ts.atm0>ts.atm2,color=C['stress'],alpha=.15,lw=0,label='역전 구간 (단기 > 장기)')
a2.set_ylabel('ATM 내재변동성 (%)'); a2.legend(frameon=False,ncol=3,loc='upper left')
for d in [CALM,STRESS]:
    dt=pd.to_datetime(d)
    for a in (a1,a2): a.axvline(dt,color='#8a8984',lw=1,ls=(0,(3,3)))
    a1.annotate(lab[d].split(':')[0],(dt,a1.get_ylim()[1]),xytext=(4,-14),textcoords='offset points',fontsize=10,color=MUTE)
a1.set_title('코스피200 지수와 ATM 내재변동성 (2025.10 – 2026.10)',loc='left',fontsize=15,color=INK,fontweight='bold')
fig.text(.01,.01,'자료: KRX. 각 날짜에서 잔존만기 7일 초과 월물 중 1·3번째 만기의 ATM IV.',fontsize=8.5,color=MUTE)
plt.tight_layout(rect=(0,.03,1,1)); plt.savefig('fig3_timeseries.png',dpi=200); plt.close()
# --- cross-check own IV (Black-76) on liquid options
r=0.0275
def b76(F,K,T,s,cp):
    d1=(np.log(F/K)+.5*s*s*T)/(s*np.sqrt(T)); d2=d1-s*np.sqrt(T)
    return np.exp(-r*T)*(F*norm.cdf(d1)-K*norm.cdf(d2) if cp=='CALL' else K*norm.cdf(-d2)-F*norm.cdf(-d1))
for d in [CALM,STRESS]:
    g,e=pick(d); g=g[(g.ACC_TRDVOL>=100)&g.m.between(.85,1.15)]; diffs=[]
    for _,x in g.iterrows():
        try: iv=brentq(lambda s:b76(x.F,x.STRIKE,x['T'],s,x.RGHT_TP_NM)-x.TDD_CLSPRC,1e-3,5)*100; diffs.append(iv-x.IMP_VOLT)
        except: pass
    out[d]['xcheck']=(len(diffs),np.median(np.abs(diffs)))
for d,v in out.items(): print(d,{k:(np.round(vv,1) if isinstance(vv,float) else vv) for k,vv in v.items()})
