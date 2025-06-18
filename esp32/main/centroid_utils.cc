#include <cmath>
#include <esp_log.h>
#include "centroid_utils.h"
#include <vector>

namespace {
    const char* TAG = "CENTROID_UTILS";
}

IntersectionPoints calculateIntersections(Point* p1, Point* p2, float r1, float r2) {
    float x1 = p1->x;
    float y1 = p1->y;
    float x2 = p2->x;
    float y2 = p2->y;
    float d = sqrt(pow(x1 - x2, 2) + pow(y1 - y2, 2));

    ESP_LOGI(TAG, "distance between points: %.2f", d);

    if (d > r1 + r2 || d < fabs(r1 - r2) || d == 0) {
      return {
        {0, 0}, 
        {0, 0}, 
        false   
      }; 
    }

    float a = (pow(r1, 2) - pow(r2, 2) + pow(d, 2)) / (2 * d);
    float h = sqrt(pow(r1, 2) - pow(a, 2));
    float x3 = x1 + a * (x2 - x1) / d;
    float y3 = y1 + a * (y2 - y1) / d;

    float x4 = x3 + h * (y2 - y1) / d;
    float y4 = y3 - h * (x2 - x1) / d;
    float x5 = x3 - h * (y2 - y1) / d;
    float y5 = y3 + h * (x2 - x1) / d;

    Point intersection1 = {x4, y4};
    Point intersection2 = {x5, y5};
    IntersectionPoints intersection = {intersection1, intersection2, true};

    return intersection;
}

Point selectIntersection(IntersectionPoints intersection, Point* p, float r) {
    float d1 = sqrt(pow(intersection.point1.x - p->x, 2) + pow(intersection.point1.y - p->y, 2));
    float d2 = sqrt(pow(intersection.point2.x - p->x, 2) + pow(intersection.point2.y - p->y, 2));
    if (d1 <= r) {
        return intersection.point1;
    } else if (d2 <= r) {
        return intersection.point2;
    } else {
        ESP_LOGW(TAG, "No valid intersection found.");
        return {0,0};
    }
}

Point calculateCentroid2Circles(Point* p1, Point* p2, float r1, float r2) {
    IntersectionPoints intersections = calculateIntersections(p1, p2, r1, r2);
    if (intersections.valid) {
        Point m = intersections.point1;
        Point n = intersections.point2;

        float xc = (m.x + n.x) / 2;
        float yc = (m.y + n.y) / 2;
        return {xc, yc};
    } else {
        ESP_LOGW(TAG, "No valid intersection found for two circles.");
        return {0, 0};
    }
}

Point calculateWeightedCentroid(Point* p1, Point* p2, Point* p3, IntersectionPoints p12, IntersectionPoints p13, IntersectionPoints p23, float r1, float r2, float r3) {
    if (p12.valid && p13.valid && p23.valid) {
      Point m = selectIntersection(p12, p3, r3);
      Point n = selectIntersection(p13, p2, r2);
      Point o = selectIntersection(p23, p1, r1);

      float a = 1/(r1+r2);
      float b = 1/(r3+r1);
      float c = 1/(r2+r3);
      float xc = (m.x*a + n.x*b + o.x*c) / (a + b + c);
      float yc = (m.y*a + n.y*b + o.y*c) / (a + b + c);

      return {xc, yc};
    } else if (p12.valid) {
      ESP_LOGW(TAG, "Using AB intersection only.");
      return calculateCentroid2Circles(p1, p2, r1, r2);
    } else if (p13.valid) {
      ESP_LOGW(TAG, "Using AC intersection only.");
      return calculateCentroid2Circles(p1, p3, r1, r3);
    } else if (p23.valid) {
      ESP_LOGW(TAG, "Using BC intersection only.");
      return calculateCentroid2Circles(p2, p3, r2, r3);
    } else {
      ESP_LOGW(TAG, "No valid centroid found.");
      return {0, 0};
    }
}


std::vector<Point> getBeaconPositions(Point* p1, Point* p2, Point* p3, float r1, float r2, float r3) {
  ESP_LOGI(TAG, "Calculating weighted centroid for points: P1(%.2f, %.2f), P2(%.2f, %.2f), P3(%.2f, %.2f)", 
    p1->x, p1->y, p2->x, p2->y, p3->x, p3->y);
  IntersectionPoints p12 = calculateIntersections(p1, p2, r1, r2);
  IntersectionPoints p13 = calculateIntersections(p1, p3, r1, r3);
  IntersectionPoints p23 = calculateIntersections(p2, p3, r2, r3);

  ESP_LOGI(TAG, "Intersections: AB valid=%d, AC valid=%d, BC valid=%d", p12.valid, p13.valid, p23.valid);

  Point centroid = calculateWeightedCentroid(p1, p2, p3, p12, p13, p23, r1, r2, r3);
  ESP_LOGI(TAG, "Calculated Centroid: x=%.4f y=%.4f", centroid.x, centroid.y);
    
  Point estimatedPosA;
  Point estimatedPosB;
  Point estimatedPosC;
  if (p12.valid && p13.valid && p23.valid) {
    estimatedPosA = Point{p1->x - centroid.x, p1->y - centroid.y};
    estimatedPosB = Point{p2->x - centroid.x, p2->y - centroid.y};
    estimatedPosC = Point{p3->x - centroid.x, p3->y - centroid.y};
  }
  else if (p12.valid) {
    estimatedPosA = Point{p1->x - centroid.x, p1->y - centroid.y};
    estimatedPosB = Point{p2->x - centroid.x, p2->y - centroid.y};
    estimatedPosC = Point{0, 0};
  }
  else if (p13.valid) {
    estimatedPosA = Point{p1->x - centroid.x, p1->y - centroid.y};
    estimatedPosB = Point{0, 0};
    estimatedPosC = Point{p3->x - centroid.x , p3->y - centroid.y};
  }
  else if (p23.valid) {
    estimatedPosA = Point{0, 0};
    estimatedPosB = Point{p2->x - centroid.x , p2->y - centroid.y};
    estimatedPosC = Point{p3->x - centroid.x, p3->y - centroid.y};
  } else {
    ESP_LOGW(TAG, "No valid intersections found, returning default positions.");
    return {Point{0, 0}, Point{0, 0}, Point{0, 0}};
  }
  ESP_LOGI(TAG, "Estimated Positions: A(%.4f, %.4f), B(%.4f, %.4f), C(%.4f, %.4f)", 
    estimatedPosA.x, estimatedPosA.y, estimatedPosB.x, estimatedPosB.y, estimatedPosC.x, estimatedPosC.y);

  return {estimatedPosA, estimatedPosB, estimatedPosC};
}