import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ImagesAPI, JobsAPI } from '../services/api';

type StatBadge = 'default' | 'success' | 'accent';

export function DashboardPage() {
  const [stats, setStats] = useState({
    instagramImages: 0,
    matches: 0,
    pendingJobs: 0,
  });

  useEffect(() => {
    async function loadStats() {
      try {
        const [instagramData, jobsData] = await Promise.all([
          ImagesAPI.listInstagram({ limit: 1, offset: 0 }),
          JobsAPI.list(),
        ]);

        const pendingCount = jobsData.filter(
          (job) => job.status === 'pending' || job.status === 'running',
        ).length;

        setStats({
          instagramImages: instagramData.total,
          matches: 0,
          pendingJobs: pendingCount,
        });
      } catch (error) {
        console.error('Failed to load stats:', error);
      }
    }
    loadStats();
  }, []);

  const statCards: Array<{
    title: string;
    value: string;
    description: string;
    link: string;
    badge: StatBadge;
  }> = [
    {
      title: 'Instagram Images',
      value: stats.instagramImages.toLocaleString(),
      description: 'Downloaded from Instagram dump',
      link: '/images',
      badge: stats.instagramImages > 0 ? 'success' : 'default',
    },
    {
      title: 'Matched Pairs',
      value: stats.matches.toLocaleString(),
      description: 'Successfully matched images',
      link: '/images',
      badge: stats.matches > 0 ? 'success' : 'default',
    },
    {
      title: 'Active Jobs',
      value: stats.pendingJobs.toLocaleString(),
      description: 'Running or queued',
      link: '/processing',
      badge: stats.pendingJobs > 0 ? 'accent' : 'default',
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-section text-text mb-2">Dashboard</h1>
        <p className="text-text-secondary">
          Match Instagram photos with your Lightroom catalog using AI vision models
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {statCards.map((stat) => (
          <Link key={stat.title} to={stat.link}>
            <Card hoverable padding="md">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{stat.title}</CardTitle>
                  <Badge variant={stat.badge}>{stat.value}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{stat.description}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div>
        <h2 className="text-card-title text-text mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link to="/images">
            <Card hoverable padding="md">
              <CardHeader>
                <CardTitle>Browse Images</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">View Instagram photos, catalog images, and matched pairs</p>
              </CardContent>
            </Card>
          </Link>

          <Link to="/processing">
            <Card hoverable padding="md">
              <CardHeader>
                <CardTitle>Start Processing</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Run vision matching or generate descriptions</p>
              </CardContent>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  );
}
