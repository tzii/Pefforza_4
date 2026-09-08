import Image from 'next/image';
import { ArrowDown, ArrowUpRight, GitBranch, MoveUpRight } from 'lucide-react';
import { Story } from '@/components/story';
import { Playground } from '@/components/playground';
import { Launchpad } from '@/components/launchpad';
import { MotionDirector } from '@/components/motion-director';
import { publicAsset } from '@/lib/site';

const repo = 'https://github.com/tzii/Pefforza_4';

export default function Home() {
  return (
    <main id="top">
      <MotionDirector />
      <a className="skip-link" href="#experiment">
        Skip to the project
      </a>
      <header className="site-header">
        <a href="#top" className="wordmark" aria-label="Pefforza 4 home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          pefforza<span className="brand-four">4</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#experiment">The project</a>
          <a href="#get-started">Get started</a>
          <a href="#play">Try the demo</a>
          <a href={repo} target="_blank" rel="noreferrer">
            GitHub <ArrowUpRight size={14} />
          </a>
        </nav>
        <a className="header-cta" href={repo} target="_blank" rel="noreferrer">
          View source <ArrowUpRight size={16} />
        </a>
      </header>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-grid" aria-hidden="true" />
        <div className="hero-topline">
          <span>
            <i className="status-dot" /> A HUMAN × MACHINE EXPERIMENT
          </span>
          <span>OPEN SOURCE. OPEN POSSIBILITIES.</span>
        </div>
        <div className="hero-copy">
          <h1 id="hero-title">
            <span>Your move.</span>
            <span className="acid">Reimagined.</span>
          </h1>
          <p>
            An open-source experiment in human × machine.
            <br />
            Connect Four, built in Python. Powered by AI,
            <br className="desktop-break" /> computer vision, and voice.
          </p>
          <div className="hero-actions">
            <a className="button button-acid" href="#experiment">
              Explore the project <ArrowDown size={20} />
            </a>
            <a className="text-link" href="#play">
              Try the browser demo <ArrowUpRight size={16} />
            </a>
          </div>
        </div>
        <div className="hero-art">
          <Image
            unoptimized
            src={publicAsset('/images/pefforza-hero.webp')}
            alt="Cobalt blue Connect Four board with sculptural red and yellow discs floating in a dark studio"
            width="1536"
            height="1024"
            fetchPriority="high"
          />
          <div className="art-coordinate">FIG. 01 / A NEW WAY TO PLAY</div>
          <div className="hero-orbit" aria-hidden="true" />
          <div className="hero-art-caption">
            <span className="status-dot" /> 6 ROWS. 7 COLUMNS. YOUR NEXT MOVE.
          </div>
        </div>
        <a className="scroll-cue" href="#experiment">
          <span className="scroll-circle">
            <ArrowDown size={17} />
          </span>
          <span>SCROLL TO EXPLORE</span>
        </a>
        <span className="hero-side-note">BUILT TO THINK. MADE TO PLAY.</span>
        <div className="hero-bottom">
          <span>01 — THE NEXT MOVE</span>
          <span>PYTHON AT HEART. CURIOUS BY DESIGN.</span>
          <span>
            V. 0.5 <span className="small-cross">✳</span>
          </span>
        </div>
      </section>
      <div className="ticker" aria-label="See it. Think ahead. Make your move.">
        <div className="ticker-track" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <span key={i}>
              SEE IT <span>✳</span> THINK AHEAD <span>✳</span> MAKE YOUR MOVE{' '}
              <span>✳</span>
            </span>
          ))}
        </div>
      </div>
      <section className="intro section-pad" id="experiment">
        <div className="section-label">
          <span>01 / THE PROJECT</span>
          <span>
            MORE THAN FOUR IN A ROW <MoveUpRight size={18} />
          </span>
        </div>
        <h2 className="intro-title">
          You know the game.
          <br />
          Meet its <span className="serif">next evolution.</span>
        </h2>
        <div className="intro-bottom">
          <span className="large-asterisk" aria-hidden="true">
            ✳
          </span>
          <p>
            A real board, a webcam, and an opponent that thinks ahead. Pefforza
            brings computer vision, search, reinforcement learning, and optional
            voice commentary into one Python project. Play in your terminal, on
            your desktop, or with a physical board.
          </p>
          <a
            className="text-link"
            href={`${repo}/blob/main/docs/PROJECT_DEEP_DIVE.md`}
            target="_blank"
            rel="noreferrer"
          >
            Inside the project <ArrowUpRight size={17} />
          </a>
        </div>
      </section>
      <Story />
      <Launchpad />
      <section id="play" className="play-section section-pad">
        <div className="section-label">
          <span>03 / THE BROWSER DEMO</span>
          <span>A LITTLE TASTE OF THE GAME.</span>
        </div>
        <Playground />
      </section>
      <footer className="site-footer section-pad">
        <div className="footer-top">
          <p>
            For the love of the game.
            <br />
            And everything behind it.
          </p>
          <a className="text-link" href={repo} target="_blank" rel="noreferrer">
            <GitBranch size={18} /> Explore the source{' '}
            <ArrowUpRight size={18} />
          </a>
        </div>
        <div className="footer-wordmark">
          pefforza<span>4</span>
          <span className="footer-star" aria-hidden="true">
            ✳
          </span>
        </div>
        <div className="footer-bottom">
          <span>AN OPEN-SOURCE CONNECT FOUR EXPERIMENT</span>
          <a
            href={`${repo}/blob/main/LICENSE`}
            target="_blank"
            rel="noreferrer"
          >
            AGPL–3.0 LICENSE ↗
          </a>
          <a href="#top">BACK TO TOP ↑</a>
        </div>
      </footer>
    </main>
  );
}
