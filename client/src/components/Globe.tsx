import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))

function WireframeGlobe() {
  const groupRef = useRef<THREE.Group>(null)

  const { outerGeo, innerGeo, particles } = useMemo(() => {
    const outerGeo = new THREE.IcosahedronGeometry(6, 2)
    const innerGeo = new THREE.IcosahedronGeometry(5.9, 2)

    // Create deterministic particles in a spherical shell.
    const particleCount = 40
    const particles: THREE.Vector3[] = []
    for (let i = 0; i < particleCount; i++) {
      const radius = 8 + ((i * 17) % 40) / 10
      const theta = i * GOLDEN_ANGLE
      const y = 1 - (2 * (i + 0.5)) / particleCount
      const radial = Math.sqrt(1 - y * y)
      particles.push(
        new THREE.Vector3(
          radius * radial * Math.cos(theta),
          radius * radial * Math.sin(theta),
          radius * y
        )
      )
    }

    return { outerGeo, innerGeo, particles }
  }, [])

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.rotation.y += 0.001
      groupRef.current.rotation.x += 0.0003
    }
  })

  return (
    <group ref={groupRef}>
      {/* Main wireframe */}
      <lineSegments>
        <edgesGeometry args={[outerGeo]} />
        <lineBasicMaterial color="#C9A84C" transparent opacity={0.4} />
      </lineSegments>

      {/* Inner glow layer */}
      <lineSegments>
        <edgesGeometry args={[innerGeo]} />
        <lineBasicMaterial color="#C9A84C" transparent opacity={0.15} />
      </lineSegments>

      {/* Particle stars */}
      {particles.map((pos, i) => (
        <mesh key={i} position={pos}>
          <sphereGeometry args={[0.03, 4, 4]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.3} />
        </mesh>
      ))}
    </group>
  )
}

export default function Globe() {
  return (
    <div
      className="absolute inset-0 pointer-events-none"
      aria-hidden="true"
      role="presentation"
      style={{ zIndex: 0 }}
    >
      <Canvas
        camera={{ position: [0, 0, 18], fov: 45 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <WireframeGlobe />
      </Canvas>
    </div>
  )
}
