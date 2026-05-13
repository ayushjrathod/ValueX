import Nav from '../components/Nav'
import BackToTop from '../components/BackToTop'
import Hero from '../sections/Hero'
import TrustBar from '../sections/TrustBar'
import FeatureShowcase from '../sections/FeatureShowcase'
import ThreePillars from '../sections/ThreePillars'
import HowItWorks from '../sections/HowItWorks'
import Testimonials from '../sections/Testimonials'
import CTAFooter from '../sections/CTAFooter'

export default function Home() {
  return (
    <main className="min-h-screen bg-cx-obsidian">
      <Nav />
      <Hero />
      <TrustBar />
      <FeatureShowcase />
      <ThreePillars />
      <HowItWorks />
      <Testimonials />
      <CTAFooter />
      <BackToTop />
    </main>
  )
}
